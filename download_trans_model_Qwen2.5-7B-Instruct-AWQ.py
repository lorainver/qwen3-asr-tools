import os
from huggingface_hub import snapshot_download

# 指定模型 ID (AWQ 量化版本)
model_id = "Qwen/Qwen2.5-7B-Instruct-AWQ"
# 指定下载路径
save_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-AWQ"

print(f"Start downloading: {model_id}")
print(f"Path: {save_path}")

try:
    snapshot_download(
        repo_id=model_id,
        local_dir=save_path,
        local_dir_use_symlinks=False,
        revision="main"
    )
    print(f"\n✓ Success: Model downloaded to {save_path}")
except Exception as e:
    print(f"\n✗ Error: {e}")
