# -*- coding: utf-8 -*-
import os
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

# 使用你已有的 GPTQ 模型，这个模型在 Windows 上兼容性最好
MODEL_PATH = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"

def test_gptq_safe():
    print(f"正在加载 GPTQ 模型 (安全模式): {MODEL_PATH}")
    
    start_time = time.time()
    
    # 加载 Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    
    # 核心：使用 transformers 原生支持加载
    # 只要安装了 optimum，就不需要编译任何东西
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"[ERROR] 加载失败: {e}")
        return
    
    load_time = time.time() - start_time
    print(f"模型加载成功，耗时: {load_time:.2f}秒")
    
    # 测试生成
    prompt = "请介绍一下你自己。"
    messages = [
        {"role": "user", "content": prompt}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    print("\nAI 回复：")
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    model.generate(
        **model_inputs,
        max_new_tokens=200,
        streamer=streamer
    )

if __name__ == "__main__":
    test_gptq_safe()
