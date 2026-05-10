import time, os, json, av
import numpy as np
import gc
import torch

def estimate_timestamps(text, cs, cd):
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
    h, m = divmod(int(s), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int(s%1*1000):03d}"

def write_srt(segments, out_path):
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
    model_path = r"D:\qwen3-asr\models\Qwen\Qwen3-ASR-0___6B"
    chunk_size = 30.0
    batch_size = 8
    
    container = av.open(str(media_path))
    total_sec = float(container.duration) / float(av.time_base)
    container.close()
    
    n_chunks = int(np.ceil(total_sec / chunk_size))
    
    if yield_progress:
        yield json.dumps({"status": "processing", "progress": 5, "message": "正在加载 Qwen3-ASR 模型..."}) + "\n"
        
    from qwen_asr import Qwen3ASRModel
    import transformers
    transformers.logging.set_verbosity_error()
    
    model = Qwen3ASRModel.from_pretrained(model_path, device_map='cuda', max_inference_batch_size=batch_size, max_new_tokens=512)
    
    if yield_progress:
        yield json.dumps({"status": "processing", "progress": 10, "message": "提取全局音频流..."}) + "\n"
        
    container = av.open(str(media_path))
    ast = container.streams.audio[0]
    resampler = av.audio.resampler.AudioResampler(format='s16', layout='mono', rate=16000)
    
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
    
    for batch_start in range(0, n_chunks, batch_size):
        batch_indices = list(range(batch_start, min(batch_start + batch_size, n_chunks)))
        batch_wavs = []
        batch_info = []
        
        for i in batch_indices:
            cs = i * chunk_size
            cd = min(chunk_size, total_sec - cs)
            chunk_path = f"D:\\qwen3-asr\\chunk_{i}.wav"
            
            start_idx = int(cs * 16000)
            end_idx = int((cs + cd) * 16000)
            chunk = full_audio[start_idx:end_idx]
            sf.write(chunk_path, chunk, 16000)
            
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
            eta = (elapsed / done_count) * (n_chunks - done_count)
            yield json.dumps({"status": "processing", "progress": percent, "message": f"正在识别 ({done_count}/{n_chunks})... 剩余 {eta/60:.1f} 分钟"}) + "\n"

    write_srt(all_segs, srt_path)
    
    del model
    gc.collect()
    torch.cuda.empty_cache()
    
    if yield_progress:
        yield json.dumps({"status": "done", "progress": 100, "message": "转录完成！", "srt_path": str(srt_path)}) + "\n"
