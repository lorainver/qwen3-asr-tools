"""
transcriber.py - 视频转字幕模块（支持取消和显存管理）

功能：
1. 使用 Qwen3-ASR 模型进行 GPU 批处理转录
2. 支持取消信号，可在转录过程中中断
3. 自动清理临时文件和 GPU 显存
"""

import time, os, json, av
import numpy as np
import gc
import torch
import logging
import tempfile
import shutil
from model_manager import model_manager
from config_loader import config

logger = logging.getLogger(__name__)


def estimate_timestamps(text, cs, cd):
    """根据字符数量估算句子时间戳"""
    import re
    if not text.strip():
        return [(cs, cs + cd, '')]
    sents = [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]
    total = sum(len(s.replace(' ', '')) for s in sents)
    if total == 0:
        return [(cs, cs + cd, text)]
    pos, result = cs, []
    for s in sents:
        dur = max(len(s.replace(' ', '')) / max(total, 1) * cd, 0.5)
        result.append((pos, pos + dur, s))
        pos += dur
    return result


def format_time(s):
    """将秒数转换为 SRT 时间格式"""
    h, m = divmod(int(s), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int(s%1*1000):03d}"


def write_srt(segments, out_path):
    """将片段列表写入 SRT 文件"""
    seen, out = set(), []
    for start, end, text in segments:
        text = ' '.join(text.split()).strip()
        if not text: continue
        key = (round(start, 2), text[:20])
        if key in seen: continue
        seen.add(key)
        out.append((start, end, text))
    with open(str(out_path), 'w', encoding='utf-8') as f:
        for i, (s, e, t) in enumerate(out, 1):
            f.write(f"{i}\n{format_time(s)} --> {format_time(e)}\n{t}\n\n")


def run_transcription(media_path, srt_path, yield_progress=None):
    """
    执行视频转字幕任务
    
    参数：
        media_path: 视频/音频文件路径
        srt_path: 输出 SRT 文件路径
        yield_progress: 是否返回进度流（用于 Web 界面）
        
    返回：
        如果 yield_progress=True，返回 JSON 格式的进度流
        支持取消：通过 model_manager.cancel() 发送取消信号
    """
    # 从配置文件读取参数
    model_path = config['models']['asr']
    chunk_size = config.get('gpu.chunk_size', 30.0)
    batch_size = config.get('gpu.batch_size', 8)
    target_sr = config.get('audio.sample_rate', 16000)
    target_format = config.get('audio.format', 's16')
    target_channels = config.get('audio.channels', 1)
    max_batch = config.get('gpu.max_inference_batch', 8)
    max_tokens = config.get('transcription.max_new_tokens', 512)
    
    model = None
    tmp_dir = tempfile.mkdtemp(prefix="qwen3_asr_")
    
    # 设置处理状态
    model_manager.set_processing(True)
    model_manager.reset_cancel()
    
    try:
        # 1. 获取视频时长
        container = av.open(str(media_path))
        total_sec = float(container.duration) / float(av.time_base)
        container.close()
        n_chunks = int(np.ceil(total_sec / chunk_size))
        
        if yield_progress:
            yield json.dumps({"status": "processing", "progress": 5, "message": "正在加载 Qwen3-ASR 模型..."}) + "\n"
        
        # 2. 加载模型
        from qwen_asr import Qwen3ASRModel
        import transformers
        transformers.logging.set_verbosity_error()
        
        logger.info(f"Loading ASR model from {model_path}")
        model = Qwen3ASRModel.from_pretrained(
            model_path, 
            device_map='cuda', 
            max_inference_batch_size=max_batch, 
            max_new_tokens=max_tokens
        )
        model_manager.register_transcriber(model)
        logger.info(f"ASR model loaded. Batch size: {max_batch}, Max tokens: {max_tokens}")
        
        if yield_progress:
            yield json.dumps({"status": "processing", "progress": 10, "message": "提取全局音频流..."}) + "\n"
        
        # 3. 提取音频
        container = av.open(str(media_path))
        ast = container.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(
            format=target_format, 
            layout=target_channels, 
            rate=target_sr
        )
        audio_frames = []
        for frame in container.decode(ast):
            for rf in resampler.resample(frame):
                audio_frames.append(rf.to_ndarray().reshape(-1))
        full_audio = np.concatenate(audio_frames)
        container.close()
        
        import soundfile as sf
        all_segs = []
        done_count = 0
        tt = time.time()
        
        logger.info(f"Starting batch processing: batch_size={batch_size}, chunk_size={chunk_size}s")
        
        # 4. 批处理转录
        for batch_start in range(0, n_chunks, batch_size):
            # 检查取消信号
            if model_manager.is_cancelled():
                logger.info("Transcription cancelled by user")
                if yield_progress:
                    yield json.dumps({"status": "cancelled", "message": "转录已被用户取消"}) + "\n"
                return
            
            batch_indices = list(range(batch_start, min(batch_start + batch_size, n_chunks)))
            batch_wavs = []
            batch_info = []
            
            for i in batch_indices:
                cs = i * chunk_size
                cd = min(chunk_size, total_sec - cs)
                chunk_path = os.path.join(tmp_dir, f"chunk_{i}.wav")
                start_idx = int(cs * target_sr)
                end_idx = int((cs + cd) * target_sr)
                chunk = full_audio[start_idx:end_idx]
                sf.write(chunk_path, chunk, target_sr)
                batch_wavs.append(chunk_path)
                batch_info.append((i, cs, cd))
                
            results = model.transcribe(audio=batch_wavs, language=None)
            if not isinstance(results, list): results = [results]
            
            for idx, res in enumerate(results):
                _, cs, cd = batch_info[idx]
                segs = list(res) if hasattr(res, '__iter__') else [res]
                full = ' '.join(str(s.text).replace('nan', ' ').replace('np.', ' ').strip() for s in segs)
                full = ' '.join(full.split())
                segs_ts = estimate_timestamps(full, cs, cd)
                all_segs.extend(segs_ts)
                done_count += 1
                
            for w in batch_wavs:
                if os.path.exists(w): os.remove(w)
                
            if yield_progress:
                percent = int((done_count / n_chunks) * 80) + 10
                elapsed = time.time() - tt
                eta = (elapsed / done_count) * (n_chunks - done_count) if done_count > 0 else 0
                logger.debug(f"Transcription progress: {done_count}/{n_chunks}, ETA: {eta/60:.1f}min")
                yield json.dumps({"status": "processing", "progress": percent, "message": f"正在识别 ({done_count}/{n_chunks})... 剩余 {eta/60:.1f} 分钟"}) + "\n"

        # 5. 写入 SRT
        write_srt(all_segs, srt_path)
        logger.info(f"Transcription completed: {srt_path}")
        
        if yield_progress:
            yield json.dumps({"status": "done", "progress": 100, "message": "转录完成！", "srt_path": str(srt_path)}) + "\n"
            
    except Exception as e:
        logger.error(f"转录出错: {e}")
        import traceback
        traceback.print_exc()
        if yield_progress:
            yield json.dumps({"status": "error", "message": f"转录出错: {e}"}) + "\n"
    finally:
        # 6. 清理临时目录、模型和显存（无论成功/失败/取消都会执行）
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.info(f"[Transcriber] 临时目录已清理: {tmp_dir}")
        except Exception:
            pass
        if model is not None:
            del model
            model_manager.unregister_transcriber()
        gc.collect()
        torch.cuda.empty_cache()
        model_manager.set_processing(False)
        logger.info("[Transcriber] 模型已清理，显存已释放")
