# -*- coding: utf-8 -*-
import os
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

# 设置模型路径
MODEL_PATH = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-AWQ"

def test_awq_model():
    print(f"正在加载 AWQ 模型: {MODEL_PATH}")
    
    start_time = time.time()
    
    # 加载 Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    
    # 加载模型
    # 注意：需要安装 autoawq
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        device_map="auto"
    )
    
    load_time = time.time() - start_time
    print(f"模型加载成功，耗时: {load_time:.2f}秒")
    
    # 测试推理
    prompt = "请介绍一下你自己。"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    print("\n生成结果：")
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=512,
        streamer=streamer
    )

if __name__ == "__main__":
    test_awq_model()
