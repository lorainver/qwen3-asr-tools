# -*- coding: utf-8 -*-
"""
使用 ExLlamaV2 测试 GPTQ 模型加载和生成速度
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import torch
from exllamav2 import (
    ExLlamaV2,
    ExLlamaV2Config,
    ExLlamaV2Cache,
    ExLlamaV2Tokenizer,
)
from exllamav2.generator import (
    ExLlamaV2StreamingGenerator,
    ExLlamaV2Sampler,
)

MODEL_PATH = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"
TEST_PROMPT = "请用100字左右介绍一下人工智能的发展历程。"
MAX_NEW_TOKENS = 100

def main():
    print("="*60)
    print("Testing GPTQ with ExLlamaV2")
    print("="*60)
    print(f"Model: {MODEL_PATH}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print()
    
    # Load config
    print("1. Loading config...")
    config = ExLlamaV2Config()
    config.model_dir = MODEL_PATH
    config.prepare()
    print(f"   Max seq len: {config.max_seq_len}")
    print(f"   Max input len: {config.max_input_len}")
    print()
    
    # Load model
    print("2. Loading model...")
    start_time = time.time()
    model = ExLlamaV2(config)
    model.load()
    load_time = time.time() - start_time
    print(f"   [OK] Model loaded in {load_time:.2f} s")
    print()
    
    # Check VRAM
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    print(f"   VRAM: {allocated:.2f} GB (alloc), {reserved:.2f} GB (reserved)")
    print()
    
    # Load tokenizer
    print("3. Loading tokenizer...")
    tokenizer = ExLlamaV2Tokenizer(config)
    print("   [OK] Tokenizer loaded")
    print()
    
    # Create cache
    print("4. Creating cache...")
    cache = ExLlamaV2Cache(model, max_seq_len=2048)
    print("   [OK] Cache created")
    print()
    
    # Create generator
    print("5. Creating generator...")
    generator = ExLlamaV2StreamingGenerator(model, cache, tokenizer)
    generator.set_stop_conditions([])
    print("   [OK] Generator created")
    print()
    
    # Format prompt for Qwen
    print("6. Testing generation...")
    prompt = f"<|im_start|>user\n{TEST_PROMPT}<|im_end|>\n<|im_start|>assistant\n"
    
    # Warmup
    print("   Warming up...")
    input_ids = tokenizer.encode(prompt)
    generator.begin_stream(input_ids, ExLlamaV2Sampler.Settings())
    for _ in range(10):
        generator.stream()
    generator.reset()
    
    # Test generation
    print("   Generating 100 tokens...")
    torch.cuda.synchronize()
    start_time = time.time()
    
    input_ids = tokenizer.encode(prompt)
    generator.begin_stream(input_ids, ExLlamaV2Sampler.Settings())
    
    generated_text = ""
    token_count = 0
    
    while token_count < MAX_NEW_TOKENS:
        chunk, eos, _ = generator.stream()
        if chunk:
            generated_text += chunk
            token_count += 1
        if eos:
            break
    
    torch.cuda.synchronize()
    end_time = time.time()
    
    total_time = end_time - start_time
    tokens_per_sec = token_count / total_time if total_time > 0 else 0
    
    print(f"   [OK] Generated {token_count} tokens in {total_time:.2f} s")
    print(f"   Speed: {tokens_per_sec:.1f} tokens/s")
    print(f"   Output: {generated_text[:60]}...")
    print()
    
    # Compare
    print("="*60)
    print("Comparison")
    print("="*60)
    print(f"ExLlamaV2 (GPTQ):  {tokens_per_sec:.1f} tokens/s")
    print(f"Transformers (3B): 10.3 tokens/s")
    print(f"Transformers (GPTQ-Int4 with CPU offload): 0.3 tokens/s")
    print()
    
    if tokens_per_sec > 5:
        print("[SUCCESS] ExLlamaV2 is working well!")
        print(f"ExLlamaV2 is {tokens_per_sec / 0.3:.0f}x faster than transformers+GPTQ")
    else:
        print("[WARNING] ExLlamaV2 is slower than expected.")
    print()
    
    # Cleanup
    del model
    del cache
    del generator
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    print("[OK] Model unloaded, VRAM freed")
    print("="*60)

if __name__ == "__main__":
    main()
