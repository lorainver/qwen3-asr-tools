import os
from huggingface_hub import snapshot_download

# 指定模型 ID
model_id = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
# 指定下载路径
save_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-Coder-1.5B-Instruct"

print(f"Start downloading translation model: {model_id}")
print(f"Path: {save_path}")

try:
    snapshot_download(
        repo_id=model_id,
        local_dir=save_path,
        local_dir_use_symlinks=False,
        revision="main"
    )
    print(f"\nSuccess: Translation model downloaded.")
except Exception as e:
    print(f"\nError: {e}")
