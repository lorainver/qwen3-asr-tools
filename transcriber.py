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
    """
    自适应音视频对齐平滑算法：
    1. 智能提取句子及其末尾的标点符号。
    2. 根据标点符号的强弱（如句号、逗号、问号）分配不同的物理停顿时间权重（0.2s - 0.5s）。
    3. 扣除停顿时间后，将剩余有效说话时间按字符字数非线性平滑均分。
    4. 确保在断句、停顿处字幕自动隐去，避免静音期无声字幕傻挂，对齐准确度大幅度提升。
    """
    import re
    if not text.strip():
        return [(cs, cs + cd, '')]

    # 分句并保留标点符号
    raw_sents = re.split(r'([。！？\n\?\!])', text)
    
    sents = []
    temp_sent = ""
    for item in raw_sents:
        if not item:
            continue
        if re.match(r'^[。！？\n\?\!]$', item):
            if temp_sent:
                sents.append((temp_sent.strip(), item))
                temp_sent = ""
            else:
                if sents:
                    last_s, last_p = sents[-1]
                    sents[-1] = (last_s, last_p + item)
        else:
            if temp_sent:
                sents.append((temp_sent.strip(), ""))
            temp_sent = item
    if temp_sent:
        sents.append((temp_sent.strip(), ""))

    sents = [(s, p) for s, p in sents if s.strip()]
    if not sents:
        return [(cs, cs + cd, text)]

    # 停顿映射表（单位：秒）
    pause_map = {
        '。': 0.45, '！': 0.45, '？': 0.45, '\n': 0.5,
        '!': 0.45, '?': 0.45, '，': 0.25, '、': 0.2, '；': 0.25
    }

    total_chars = sum(len(s.replace(' ', '')) for s, _ in sents)
    if total_chars == 0:
        return [(cs, cs + cd, text)]

    total_pause_time = 0.0
    sent_pauses = []
    for idx, (s, p) in enumerate(sents):
        pause_val = 0.0
        if p:
            char = p[0]
            pause_val = pause_map.get(char, 0.4)
        else:
            commas = len(re.findall(r'[，,、；;]', s))
            pause_val = commas * 0.2

        pause_val = min(pause_val, 1.2)
        if idx == len(sents) - 1:
            # 最后一个句子的切片尾部停顿限制
            pause_val = min(pause_val, 0.3)
            
        sent_pauses.append(pause_val)
        total_pause_time += pause_val

    # 停顿保护上限：总停顿不超过本段总时长的 50%
    if total_pause_time > cd * 0.5:
        scale = (cd * 0.5) / total_pause_time
        sent_pauses = [p * scale for p in sent_pauses]
        total_pause_time = cd * 0.5

    active_time = cd - total_pause_time
    
    result = []
    curr_time = cs
    for idx, (s, p) in enumerate(sents):
        char_len = len(s.replace(' ', ''))
        speak_dur = (char_len / total_chars) * active_time
        speak_dur = max(speak_dur, 0.3) # 句发音最短 0.3 秒
        
        start_time = curr_time
        end_time = curr_time + speak_dur
        
        full_text = s + p
        result.append((start_time, end_time, full_text))
        
        # 巧妙留白：时间轴加上停顿，生成完美的静音隐去效果
        curr_time = end_time + sent_pauses[idx]

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
            yield json.dumps({"status": "processing", "progress": 5, "message": "检测显存并释放冲突模型..."}) + "\n"
        
        # 1.5 显存互斥锁：确保 LLM 模型已被释放以腾空 VRAM 给 ASR 模型
        model_manager.prepare_for_transcription()
        
        if yield_progress:
            yield json.dumps({"status": "processing", "progress": 7, "message": "正在加载 Qwen3-ASR 模型..."}) + "\n"
            
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
        
        # 3. 流式提取音频到临时文件（极省内存）
        temp_pcm_path = os.path.join(tmp_dir, "full_audio.raw")
        container = av.open(str(media_path))
        if not container.streams.audio:
            raise ValueError("找不到音频流")
        ast = container.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(
            format=target_format, 
            layout=target_channels, 
            rate=target_sr
        )
        
        with open(temp_pcm_path, 'wb') as f:
            for frame in container.decode(ast):
                for rf in resampler.resample(frame):
                    f.write(rf.to_ndarray().tobytes())
        container.close()
        
        # 使用内存映射 np.memmap 加载音频文件，实现 0 内存占用
        dtype_map = {'s16': np.int16, 'flt': np.float32, 's32': np.int32}
        audio_dtype = dtype_map.get(target_format, np.int16)
        full_audio = np.memmap(temp_pcm_path, dtype=audio_dtype, mode='r')
        
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
            if 'full_audio' in locals() and hasattr(full_audio, '_mmap'):
                full_audio._mmap.close()
        except Exception:
            pass
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
