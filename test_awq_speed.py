# -*- coding: utf-8 -*-
"""
测试 AWQ 模型加载和生成速度
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 禁用 Triton
os.environ['TORCH_COMPILE_DISABLE'] = '1'

import torch
torch._dynamo.config.disable = True

from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig

MODEL_PATH = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-AWQ"
TEST_PROMPT = "请用100字左右介绍一下人工智能的发展历程。"
MAX_NEW_TOKENS = 100

def get_gpu_memory():
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    return allocated, reserved

def main():
    print("="*60)
    print("Testing AWQ Model: Qwen2.5-7B-Instruct-AWQ")
    print("="*60)
    print(f"Model path: {MODEL_PATH}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print()
    
    # Check config
    print("1. Checking model config...")
    try:
        config = AutoConfig.from_pretrained(MODEL_PATH)
        print(f"   Model type: {config.model_type}")
        if hasattr(config, 'quantization_config'):
            print(f"   Quantization: {config.quantization_config}")
        else:
            print("   No quantization_config found")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return
    print()
    
    # Load tokenizer
    print("2. Loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        print("   [OK] Tokenizer loaded")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return
    print()
    
    # Load model
    print("3. Loading model...")
    start_time = time.time()
    try:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            device_map="auto",
            trust_remote_code=True,
        )
        load_time = time.time() - start_time
        allocated, reserved = get_gpu_memory()
        print(f"   [OK] Model loaded in {load_time:.2f} s")
        print(f"   VRAM: {allocated:.2f} GB (alloc), {reserved:.2f} GB (reserved)")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return
    print()
    
    # Test generation
    print("4. Testing generation...")
    messages = [{"role": "user", "content": TEST_PROMPT}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    # Warmup
    print("   Warming up...")
    with torch.no_grad():
        _ = model.generate(**inputs, max_new_tokens=10, do_sample=False)
    
    # Test
    print("   Generating 100 tokens...")
    torch.cuda.synchronize()
    start_time = time.time()
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    
    torch.cuda.synchronize()
    end_time = time.time()
    
    input_len = inputs['input_ids'].shape[1]
    output_len = outputs.shape[1]
    generated_tokens = output_len - input_len
    
    total_time = end_time - start_time
    tokens_per_sec = generated_tokens / total_time
    
    response = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)
    
    print(f"   [OK] Generated {generated_tokens} tokens in {total_time:.2f} s")
    print(f"   Speed: {tokens_per_sec:.1f} tokens/s")
    print(f"   Output: {response[:60]}...")
    print()
    
    # Compare with GPTQ
    print("="*60)
    print("Comparison with GPTQ-Int4 (from previous test)")
    print("="*60)
    print(f"AWQ speed:      {tokens_per_sec:.1f} tokens/s")
    print(f"GPTQ-Int4 speed: 0.3 tokens/s (CPU offload)")
    print(f"AWQ is {tokens_per_sec / 0.3:.1f}x faster than GPTQ-Int4")
    print()
    
    # Cleanup
    del model
    del tokenizer
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    print("[OK] Model unloaded, VRAM freed")
    print("="*60)

if __name__ == "__main__":
    main()