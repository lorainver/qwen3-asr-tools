#!/usr/bin/env python3
"""下载 Qwen3-ASR-0.6B 模型到 D 盘"""
from modelscope import snapshot_download

model_dir = snapshot_download(
    'Qwen/Qwen3-ASR-0.6B',
    cache_dir='D:\\qwen3-asr\\models'
)
print(f"模型已下载到: {model_dir}")
