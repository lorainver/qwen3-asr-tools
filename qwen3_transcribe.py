#!/usr/bin/env python3
"""
Qwen3-ASR 字幕生成脚本
用法: python qwen3_transcribe.py <音视频文件> [--model 0.6B|1.7B] [--lang zh|en|auto] [--device cpu|cuda]
"""
import argparse
import sys
import time
from pathlib import Path


def format_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    parser = argparse.ArgumentParser(description="Qwen3-ASR 字幕生成工具")
    parser.add_argument("audio", help="音频/视频文件路径")
    parser.add_argument("--model", default="0.6B", choices=["0.6B", "1.7B"],
                        help="模型大小 (默认: 0.6B)")
    parser.add_argument("--lang", default=None,
                        help="语言代码 (zh/en/Sichuan/auto，默认自动检测)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="推理设备 (默认: cpu)")
    parser.add_argument("--model_dir", default="D:\\qwen3-asr\\models",
                        help="模型缓存目录")
    parser.add_argument("--output", default=None,
                        help="输出 SRT 文件路径 (默认: 音频文件名_模型名.srt)")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"错误: 文件不存在 - {audio_path}")
        sys.exit(1)

    model_name = f"Qwen/Qwen3-ASR-{args.model}"

    # 默认输出文件名
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = audio_path.with_name(f"{audio_path.stem}_{args.model}.srt")

    print("=== Qwen3-ASR 字幕生成 ===")
    print(f"音频:   {audio_path}")
    print(f"模型:   {model_name}")
    print(f"设备:   {args.device}")
    print(f"语言:   {args.lang or '自动检测'}")
    print(f"输出:   {output_path}")
    print("加载模型中...")

    import torch
    from qwen_asr import Qwen3ASRModel

    # 加载模型
    dtype = torch.bfloat16 if args.device == "cuda" else torch.float32
    model = Qwen3ASRModel.from_pretrained(
        model_name,
        dtype=dtype,
        device_map=args.device,
        max_inference_batch_size=32,
        max_new_tokens=256,
        cache_dir=args.model_dir,
    )

    print("模型加载完成，开始转录...")
    start_time = time.time()

    results = model.transcribe(
        audio=str(audio_path),
        language=args.lang,
    )

    elapsed = time.time() - start_time

    # 处理结果
    segments = results.segments if hasattr(results, 'segments') else results
    seg_list = list(segments)

    print(f"时长: {elapsed:.1f}s ({elapsed/60:.1f}min) | 段数: {len(seg_list)}")

    # 写入 SRT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(seg_list, 1):
            start = seg.start if hasattr(seg, 'start') else seg.get('start', 0)
            end = seg.end if hasattr(seg, 'end') else seg.get('end', 0)
            text = seg.text if hasattr(seg, 'text') else seg.get('text', '')

            f.write(f"{i}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text.strip()}\n\n")

    print(f"完成！字幕已保存至: {output_path}")


if __name__ == "__main__":
    main()
