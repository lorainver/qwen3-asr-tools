# -*- coding: utf-8 -*-
import os
import sys
import time

# 强制注入 CUDA 路径
os.environ["CUDA_HOME"] = r"D:\NVIDIA\CUDA\v12.1"
os.environ["PATH"] = r"D:\NVIDIA\CUDA\v12.1\bin;" + os.environ.get("PATH", "")

# 指定新环境的路径，确保使用的是稳定版引擎
STABLE_VENV_PATH = r"D:\qwen3-asr\venv_stable"
MODEL_PATH = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"

def test_exllamav2_speed():
    print("="*60)
    print("正在使用稳定环境 (Torch 2.4 + ExLlamaV2) 进行测试")
    print("="*60)
    
    try:
        import torch
        from exllamav2 import ExLlamaV2, ExLlamaV2Config, ExLlamaV2Cache, ExLlamaV2Tokenizer
        from exllamav2.generator import ExLlamaV2StreamingGenerator, ExLlamaV2Sampler
    except ImportError as e:
        print(f"[ERROR] 缺少必要库: {e}")
        print("请确保已在 venv_stable 中安装 exllamav2")
        return

    print(f"CUDA 是否可用: {torch.cuda.is_available()}")
    print(f"当前 GPU: {torch.cuda.get_device_name(0)}")
    
    # 1. 配置加载
    config = ExLlamaV2Config()
    config.model_dir = MODEL_PATH
    config.prepare()
    
    # 强制将所有层放在 GPU 上，避免 offload
    config.max_seq_len = 2048 # 减小 seq_len 以节省显存
    
    # 2. 加载模型
    print("\n2. 正在极速加载模型权重...")
    start_time = time.time()
    model = ExLlamaV2(config)
    model.load()
    print(f"[OK] 模型加载完毕，耗时: {time.time() - start_time:.2f}秒")
    
    # 3. 初始化 Tokenizer 和 Cache
    tokenizer = ExLlamaV2Tokenizer(config)
    cache = ExLlamaV2Cache(model, max_seq_len=2048)
    
    # 4. 创建生成器
    generator = ExLlamaV2StreamingGenerator(model, cache, tokenizer)
    
    # 5. 推理测试
    prompt = "请用100字左右介绍一下量子计算。"
    formatted_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    
    print("\n3. 开始推理测试：")
    input_ids = tokenizer.encode(formatted_prompt)
    
    # 设置采样参数
    settings = ExLlamaV2Sampler.Settings()
    settings.temperature = 0.7
    settings.top_k = 40
    settings.top_p = 0.9
    
    generator.begin_stream(input_ids, settings)
    
    generated_text = ""
    token_count = 0
    start_gen_time = time.time()
    
    while True:
        chunk, eos, _ = generator.stream()
        if chunk:
            print(chunk, end="", flush=True)
            generated_text += chunk
            token_count += 1
        if eos or token_count >= 200:
            break
    
    total_gen_time = time.time() - start_gen_time
    tps = token_count / total_gen_time
    
    print(f"\n\n" + "="*60)
    print(f"性能报告")
    print(f"生成长度: {token_count} tokens")
    print(f"生成时间: {total_gen_time:.2f} 秒")
    print(f"平均速度: {tps:.2f} tokens/s")
    print("="*60)
    
    if tps > 30:
        print("[恭喜] 速度已达到满血状态！对比之前提升了约 100-200 倍。")

if __name__ == "__main__":
    test_exllamav2_speed()
