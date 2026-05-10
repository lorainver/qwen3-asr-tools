#!/usr/bin/env python3
"""
Qwen3-ASR 全量转录 - 分段 + 续跑支持 + 近似时间戳
- 每完成一段立即写入SRT（断点保护）
- 启动时从 checkpoint 恢复，支持中断后继续
- PyAV: 直接编码 resampler 输出的 flt 帧到 PCM，无需手动 AudioFrame
"""
import argparse, sys, time, os, json, av, numpy as np
from pathlib import Path

def format_time(s):
    h, m = divmod(int(s), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int(s%1*1000):03d}"

def extract_wav_from_array(audio_array, samplerate, start_sec, dur_sec, out_path):
    """Slices a pre-loaded numpy array and saves to wav."""
    import soundfile as sf
    start_idx = int(start_sec * samplerate)
    end_idx = int((start_sec + dur_sec) * samplerate)
    chunk = audio_array[start_idx:end_idx]
    sf.write(out_path, chunk, samplerate)

def estimate_timestamps(text, cs, cd):
    """Estimate word timestamps by splitting on Chinese punctuation."""
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

def write_srt(segments, out_path):
    """Write SRT with deduplication by time+text."""
    seen, out = set(), []
    for start, end, text in segments:
        text = ' '.join(text.split()).strip()
        if not text:
            continue
        key = (round(start, 2), text[:20])
        if key in seen:
            continue
        seen.add(key)
        out.append((start, end, text))
    with open(str(out_path), 'w', encoding='utf-8') as f:
        for i, (s, e, t) in enumerate(out, 1):
            f.write(f"{i}\n{format_time(s)} --> {format_time(e)}\n{t}\n\n")
    return out # 返回去重后的段落用于写txt

def write_txt(segments, out_path):
    """Write plain text."""
    with open(str(out_path), 'w', encoding='utf-8') as f:
        for _, _, text in segments:
            f.write(text + "\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="输入媒体文件 (视频或音频)")
    p.add_argument("--chunk", type=float, default=30)
    p.add_argument("--model_dir", default=r"D:\qwen3-asr\models")
    p.add_argument("--output", default=None, help="输出SRT路径 (可选)")
    p.add_argument("--resume", action="store_true", help="从 checkpoint 继续")
    p.add_argument("--batch", type=int, default=8, help="批处理大小，一次处理多少段")
    args = p.parse_args()

    media_file = Path(args.input)
    srt_path = Path(args.output) if args.output else media_file.with_name(f"{media_file.stem}_qwen3.srt")
    txt_path = srt_path.with_suffix(".txt")
    ckpt_path = media_file.with_name(f"{media_file.stem}_qwen3_ckpt.json")
    model_path = str(Path(args.model_dir) / "Qwen" / "Qwen3-ASR-0___6B")

    # Duration
    container = av.open(str(media_file))
    total_sec = float(container.duration) / float(av.time_base)
    container.close()

    n = int(np.ceil(total_sec / args.chunk))
    print("=" * 60)
    print(f"  Qwen3-ASR GPU 批处理模式 (Batch Size: {args.batch})")
    print(f"  文件: {media_file.name}  |  时长: {total_sec:.1f}s")
    print(f"  配置: {n} 段 x {args.chunk}s")
    print("=" * 60)

    # Resume from checkpoint
    all_segs, done = [], set()
    if args.resume and ckpt_path.exists():
        ckpt = json.loads(ckpt_path.read_text(encoding='utf-8'))
        all_segs = ckpt['segments']
        done = set(ckpt['done'])
        print(f"恢复进度: {len(done)}/{n} 已完成")

    # 记录初始完成数用于计算 ETA
    initial_done_count = len(done)

    # Load model
    t0 = time.time()
    from qwen_asr import Qwen3ASRModel
    import transformers
    transformers.logging.set_verbosity_error()
    
    model = Qwen3ASRModel.from_pretrained(model_path, device_map='cuda', max_inference_batch_size=args.batch, max_new_tokens=512)
    print(f"模型加载完毕: {time.time()-t0:.1f}s")

    # 1. 一次性提取全量音频（加速核心）
    print("正在预提取全局音频...")
    container = av.open(str(media_file))
    if not container.streams.audio:
        print("错误: 找不到音频流")
        return
    ast = container.streams.audio[0]
    resampler = av.audio.resampler.AudioResampler(format='s16', layout='mono', rate=16000)
    
    audio_frames = []
    for frame in container.decode(ast):
        for rf in resampler.resample(frame):
            audio_frames.append(rf.to_ndarray().reshape(-1))
    full_audio = np.concatenate(audio_frames)
    container.close()
    print(f"音频提取完毕，开始转录...")

    tt = time.time()
    
    # 批量处理逻辑
    for batch_start in range(0, n, args.batch):
        batch_indices = [i for i in range(batch_start, min(batch_start + args.batch, n)) if i not in done]
        if not batch_indices:
            continue

        batch_wavs = []
        batch_info = []

        # 2. 内存切片（毫秒级）
        for i in batch_indices:
            cs, cd = i * args.chunk, min(args.chunk, total_sec - i * args.chunk)
            chunk_path = f"D:\\qwen3-asr\\chunk_{i}.wav"
            extract_wav_from_array(full_audio, 16000, cs, cd, chunk_path)
            batch_wavs.append(chunk_path)
            batch_info.append((i, cs, cd))

        try:
            t1 = time.time()
            # 3. 批量推理
            results = model.transcribe(audio=batch_wavs, language=None)
            
            # 处理结果（针对单条和多条返回值的兼容处理）
            if not isinstance(results, list):
                results = [results]

            for idx, res in enumerate(results):
                real_idx, cs, cd = batch_info[idx]
                
                # 提取文本
                segs = list(res) if hasattr(res, '__iter__') else [res]
                full = ' '.join(str(s.text).replace('nan', ' ').replace('np.', ' ').strip() for s in segs)
                full = ' '.join(full.split())

                # 估算时间戳并加入
                segs_ts = estimate_timestamps(full, cs, cd)
                all_segs.extend(segs_ts)
                done.add(real_idx)

            # 3. 清理临时文件
            for w in batch_wavs:
                if os.path.exists(w):
                    os.remove(w)

            # 4. 单行显示进度
            dt = time.time() - t1
            rtf = dt / (len(batch_indices) * args.chunk)
            percent = (len(done) / n) * 100
            
            # 计算剩余时间 (ETA)
            elapsed_now = time.time() - tt
            current_session_done = len(done) - initial_done_count
            eta = (elapsed_now / current_session_done) * (n - len(done)) / 60 if current_session_done > 0 else 0
            
            sys.stdout.write(f"\r  进度: {percent:>5.1f}% | 段数: {len(done)}/{n} | 批耗时: {dt:.1f}s | ETA: {eta:.1f}min    ")
            sys.stdout.flush()

            # 5. 定时保存
            ckpt_path.write_text(json.dumps({'segments': all_segs, 'done': list(done)}, ensure_ascii=False), encoding='utf-8')
            write_srt(all_segs, srt_path)

        except Exception as e:
            print(f"\n  [ERROR] 批处理失败: {e}")
            for w in batch_wavs:
                if os.path.exists(w): os.remove(w)

    elapsed = time.time() - tt
    print(f"\n" + "-" * 60)
    print(f"总计完成: {len(all_segs)} 段字幕 | 总耗时: {elapsed/60:.1f}min | RTF={elapsed/total_sec:.2f}x")
    
    # 写入最终结果
    final_segs = write_srt(all_segs, srt_path)
    write_txt(final_segs, txt_path)
    
    if ckpt_path.exists():
        ckpt_path.unlink()
    print(f"最终输出 SRT: {srt_path}")
    print(f"最终输出 TXT: {txt_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()