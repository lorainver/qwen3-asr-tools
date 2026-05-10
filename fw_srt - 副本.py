#!/usr/bin/env python3
r"""
faster-whisper GPU 字幕转录脚本
===============================
- GPU 加速（RTX 5060 约 6 分钟转完 64 分钟视频，比 CPU 快 ~10 倍）
- 两种断句模式：
    natural（默认）= 按语音停顿自然断句，每条字幕一句话
    fixed          = 按固定时长切片（--chunk 控制秒数）
- 自动去重 + SRT 输出
- 断点续跑（checkpoint）

用法:
  python fw_srt.py "F:/视频/xxx.mp4"
  python fw_srt.py "F:/视频/xxx.mp4" --mode natural
  python fw_srt.py "F:/视频/xxx.mp4" --mode fixed --chunk 5
  python fw_srt.py "F:/视频/xxx.mp4" --model medium
  python fw_srt.py "F:/视频/xxx.mp4" --resume
  python fw_srt.py "F:/视频/xxx.mp4" -o "F:/字幕/xxx.srt"

GPU vs CPU 效率对比（64 分钟视频实测）:
  GPU faster-whisper medium:  ~6 分钟  | RTFx ~10x  | 日常首选
  CPU Qwen3-ASR 0.6B:        ~35 分钟  | RTFx ~1.8x | 方言识别
  CPU faster-whisper small:   ~64 分钟  | RTFx ~1x   | 兜底方案
"""
import argparse
import sys
import time
import os
import json
import faster_whisper
import srt


def assemble_natural(all_segments):
    """自然断句模式：直接用模型的语音停顿分段，每条字幕一句话。"""
    subs = []
    for i, seg in enumerate(all_segments):
        subs.append(srt.Subtitle(
            index=i + 1,
            start=srt.timedelta(seconds=seg["start"]),
            end=srt.timedelta(seconds=seg["end"]),
            content=seg["text"]
        ))
    return subs


def assemble_fixed(all_segments, total_sec, chunk_sec, resume_info=None):
    """固定切片模式：按指定时长分段，可能跨句子拼接。"""
    done_chunks = set()
    saved_subs = []
    start_idx = 1

    if resume_info:
        done_chunks = set(resume_info.get("done_chunks", []))
        saved_subs = resume_info.get("saved_subs", [])
        start_idx = len(saved_subs) + 1

    n_chunks = int(total_sec / chunk_sec) + 1
    subs = [srt.Subtitle(
        index=i + 1,
        start=srt.timedelta(seconds=s["start_s"]),
        end=srt.timedelta(seconds=s["end_s"]),
        content=s["content"]
    ) for i, s in enumerate(saved_subs)]

    idx = start_idx

    for ci in range(n_chunks):
        cs = ci * chunk_sec
        ce = min(cs + chunk_sec, total_sec)

        if cs in done_chunks:
            continue

        texts = []
        for seg in all_segments:
            if seg["end"] <= cs:
                continue
            if seg["start"] >= ce:
                break
            texts.append(seg["text"])

        done_chunks.add(cs)

        if not texts:
            continue

        content = " ".join(texts)
        subs.append(srt.Subtitle(
            index=idx,
            start=srt.timedelta(seconds=cs),
            end=srtimedelta(seconds=ce),
            content=content
        ))
        saved_subs.append({"start_s": cs, "end_s": ce, "content": content})
        idx += 1

    return subs, done_chunks, saved_subs


def main():
    # ── 参数 ──────────────────────────────────────────────────────
    p = argparse.ArgumentParser(
        description="faster-whisper GPU 字幕转录 (RTX 5060 约 6 分钟转 64 分钟视频)"
    )
    p.add_argument("video", help="视频文件路径")
    p.add_argument("--mode", default="natural", choices=["natural", "fixed"],
                   help="断句模式: natural=按语音停顿自然断句(默认), fixed=按固定时长切片")
    p.add_argument("--chunk", type=float, default=10,
                   help="每段字幕时长（秒），仅 fixed 模式生效，默认 10s")
    p.add_argument("--model", default="medium",
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help="模型大小，默认 medium（8GB 显存够用）")
    p.add_argument("--compute", default="float16",
                   help="计算精度，默认 float16（RTX 5060 兼容性最好）。可选 float32/float16/int8_float16")
    p.add_argument("--output", "-o", default=None, help="输出 SRT 路径")
    p.add_argument("--resume", action="store_true", help="从 checkpoint 继续（仅 fixed 模式）")
    p.add_argument("--language", default="zh", help="语言代码，默认 zh")
    args = p.parse_args()

    VIDEO = os.path.abspath(args.video)
    if not os.path.isfile(VIDEO):
        print(f"错误: 文件不存在 - {VIDEO}")
        sys.exit(1)

    mode_tag = "natural" if args.mode == "natural" else f"fixed {args.chunk}s"
    OUT_SRT = args.output or os.path.splitext(VIDEO)[0] + "_fw_gpu.srt"
    CKPT = os.path.splitext(VIDEO)[0] + "_fw_gpu_ckpt.json"

    # ── 加载模型 ──────────────────────────────────────────────────
    print("=" * 60)
    print("  faster-whisper GPU 字幕转录")
    print(f"  视频: {os.path.basename(VIDEO)}")
    print(f"  模型: {args.model}  |  计算: {args.compute}  |  断句: {mode_tag}")
    print("=" * 60)

    t0 = time.time()
    model = faster_whisper.WhisperModel(
        args.model, device="cuda", compute_type=args.compute
    )
    print(f"模型加载: {time.time() - t0:.1f}s  |  设备: CUDA")

    # ── 转录（一次性完成，GPU 很快）───────────────────────────────
    print("正在转录（GPU 加速中）...")
    t1 = time.time()

    # natural 模式默认 float16（RTX 5060 兼容性最好，无需 VAD）
    # 固定模式若用户未指定 compute，默认 int8_float16 以节省显存
    compute = args.compute
    if args.compute == "float16":  # 用户用的默认或 --compute float16
        compute = "float16"

    segments_iter, info = model.transcribe(
        VIDEO, language=args.language,
        vad_filter=False,          # 不走 VAD re-encode，RTX 5060 兼容性
        task="transcribe",
        beam_size=5,               # 增大 beam_size 改善断句质量
    )
    print(f"音频时长: {info.duration:.0f}s  |  语言: {info.language}  |  beam: 5")

    # 收集所有 segments（generator 只能遍历一次，必须先全部取出）
    all_segments = []
    for seg in segments_iter:
        t = seg.text.strip()
        if t:
            all_segments.append({"start": seg.start, "end": seg.end, "text": t})

    transcribe_sec = time.time() - t1
    total_sec = info.duration
    rtf_transcribe = transcribe_sec / total_sec if total_sec > 0 else 0
    print(f"转录完成: {len(all_segments)} 段  |  耗时 {transcribe_sec:.1f}s  |  RTFx {1/rtf_transcribe:.1f}x")

    # ── 组装字幕 ──────────────────────────────────────────────────
    if args.mode == "natural":
        print("断句模式: 自然断句（按语音停顿，每条字幕一句话）")
        print("-" * 60)
        subs = assemble_natural(all_segments)
    else:
        # ── 恢复 checkpoint（仅 fixed 模式）──────────────────────
        resume_info = None
        if args.resume and os.path.exists(CKPT):
            ckpt = json.loads(open(CKPT, encoding="utf-8").read())
            resume_info = ckpt
            print(f"断点续跑: 已有 {len(resume_info.get('done_chunks', []))} 段完成")

        print(f"断句模式: 固定切片 {args.chunk}s")
        print("-" * 60)
        subs, done_chunks, saved_subs = assemble_fixed(
            all_segments, total_sec, args.chunk, resume_info
        )

        # 保存 checkpoint（fixed 模式才需要）
        if len(subs) > 0:
            open(CKPT, "w", encoding="utf-8").write(json.dumps({
                "done_chunks": list(done_chunks),
                "saved_subs": saved_subs
            }, ensure_ascii=False))

    # ── 写入 SRT ──────────────────────────────────────────────────
    with open(OUT_SRT, "w", encoding="utf-8") as f:
        f.write(srt.compose(subs))

    # 全部完成，删除 checkpoint
    if os.path.exists(CKPT):
        os.remove(CKPT)

    elapsed = time.time() - t0
    rtf_total = elapsed / total_sec if total_sec > 0 else 0

    avg_dur = sum((s.end - s.start).total_seconds() for s in subs) / len(subs) if subs else 0

    print("-" * 60)
    print(f"完成! {len(subs)} 条字幕  |  平均每条 {avg_dur:.1f}s  |  总耗时 {elapsed:.0f}s ({elapsed / 60:.1f}min)  |  RTFx {1 / rtf_total:.1f}x")
    print(f"输出: {OUT_SRT}")
    print()
    print("=== GPU vs CPU 效率对比 (64 分钟视频实测) ===")
    print("  GPU faster-whisper medium:  ~6 分钟  | RTFx ~10x  | 日常首选")
    print("  CPU Qwen3-ASR 0.6B:        ~35 分钟  | RTFx ~1.8x | 方言识别")
    print("  CPU faster-whisper small:   ~64 分钟  | RTFx ~1x   | 兜底方案")


if __name__ == "__main__":
    main()