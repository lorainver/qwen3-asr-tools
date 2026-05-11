import os
import json
import shutil

model_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-3B-Instruct"
config_file = os.path.join(model_path, "config.json")

print(f"--- 正在检查模型文件夹: {model_path} ---")

if not os.path.exists(config_file):
    print(f"❌ 错误: 找不到配置文件 {config_file}")
else:
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    quant_info = config.get("quantization_config")
    if quant_info:
        print(f"⚠️ 发现配置冲突! config.json 中包含量化信息: {quant_info}")
        if quant_info.get("quant_method") == "awq":
            print("❗ 检测到 AWQ 标记。正在尝试移除该标记以强制使用 bitsandbytes 加载...")
            del config["quantization_config"]
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            print("✅ 修复完成: 已从 config.json 中移除 AWQ 冲突配置。")
        else:
            print("该量化配置不是 AWQ，无需处理。")
    else:
        print("✅ 检查通过: config.json 中没有冲突的量化信息。")

# 检查是否有残余的加载器文件
awq_files = ["quantize_config.json"]
for f in awq_files:
    fp = os.path.join(model_path, f)
    if os.path.exists(fp):
        print(f"⚠️ 发现 AWQ 特有文件: {f}，正在将其重命名为备份文件...")
        os.rename(fp, fp + ".bak")
        print(f"✅ 已屏蔽 {f}")

print("\n--- 检查完毕，请尝试重新启动 uvicorn 服务 ---")
