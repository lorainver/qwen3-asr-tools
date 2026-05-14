import os
from huggingface_hub import snapshot_download

model_id = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
save_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"

print(f"Start downloading: {model_id}")
print(f"Path: {save_path}")

try:
 snapshot_download(
 repo_id=model_id,
 local_dir=save_path,
 local_dir_use_symlinks=False,
 revision="main"
 )
 print(f"\nSuccess: Model downloaded.")
except Exception as e:
 print(f"\nError: {e}")