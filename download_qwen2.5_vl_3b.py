import os
from huggingface_hub import snapshot_download

# 模型 ID：Qwen2.5-VL 系列的 3B 增强版（视觉多模态）
model_id = "Qwen/Qwen2.5-VL-3B-Instruct"

# 指定保存路径
save_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-VL-3B-Instruct"

print(f"开始下载 Qwen2.5-VL 视觉大模型: {model_id}")
print(f"保存路径: {save_path}")

if not os.path.exists(save_path):
    os.makedirs(save_path, exist_ok=True)

try:
    snapshot_download(
        repo_id=model_id,
        local_dir=save_path,
        local_dir_use_symlinks=False,
        # 视觉模型文件较多，忽略一些不必要的格式（如果存在的话）
        ignore_patterns=["*.msgpack", "*.h5", "tf_*"]
    )
    print("\n✅ Success: Qwen2.5-VL 模型下载完成！")
    print(f"现在你可以将其路径配置到 config.yaml 中使用了。")
except Exception as e:
    print(f"\n❌ Error: 下载过程中出错: {e}")
