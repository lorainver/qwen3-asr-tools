import os
from huggingface_hub import snapshot_download

# 指定 D 盘存储路径
model_dir = r"D:\qwen3-asr\models\Qwen\Qwen3-ASR-1___7B"
os.makedirs(model_dir, exist_ok=True)

print(f"正在下载 Qwen3-ASR-1.7B 模型到: {model_dir}")
print("这可能需要几分钟，请保持网络畅通...")

try:
    snapshot_download(
        repo_id="Qwen/Qwen3-ASR-1.7B",
        local_dir=model_dir,
        local_dir_use_symlinks=False,
        revision="main"
    )
    print("\n恭喜！1.7B 模型下载完成。")
except Exception as e:
    print(f"\n下载失败: {e}")
    print("建议检查网络环境，或尝试使用代理。")
