#!/usr/bin/env python3
"""用 ffmpeg 截取前60秒测试"""
import subprocess
import sys

inp = "C:\\Users\\songc\\AppData\\Local\\Temp\\whisper_test.mp4"
out = "C:\\Users\\songc\\AppData\\Local\\Temp\\qwen3_test_60s.mp4"

cmd = [
    "ffmpeg", "-y", "-i", inp,
    "-t", "60", "-c", "copy", out
]
print(f"截取前60秒: {inp} -> {out}")
subprocess.run(cmd, check=True)
print("完成！")
