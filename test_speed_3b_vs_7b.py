# -*- coding: utf-8 -*-
"""
测试 3B vs 7B 模型生成速度对比

测试内容：
1. 加载时间
2. 生成速度（tokens/s）
3. 显存占用
"""

import os
import time
import gc
import sys

# 修复 Windows 控制台编码
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 禁用 Triton JIT（Windows 不支持）
os.environ['TORCH_COMPILE_DISABLE'] = '1'

import torch
torch._dynamo.config.disable = True

from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig, BitsAndBytesConfig

# 测试配置
TEST_PROMPT = "请用100字左右介绍一下人工智能的发展历程。"
MAX_NEW_TOKENS = 100
NUM_RUNS = 3

# 模型配置
MODELS = {
    "3B": {
        "name": "Qwen2.5-3B-Instruct",
        "path": r"D:\qwen3-asr\models\Qwen\Qwen2.5-3B-Instruct",
        "quantization": "BitsAndBytes-Int4"
    },
    "7B": {
        "name": "Qwen2.5-7B-Instruct-GPTQ-Int4",
        "path": r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4",
        "quantization": "GPTQ-Int4"
    }
}


def get_gpu_memory():
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    return allocated, reserved


def load_model(model_id):
    model_info = MODELS[model_id]
    print(f"\n{'='*60}")
    print(f"Loading: {model_info['name']}")
    print(f"Quantization: {model_info['quantization']}")
    print(f"{'='*60}")
    
    gc.collect()
    torch.cuda.empty_cache()
    
    start_time = time.time()
    
    tokenizer = AutoTokenizer.from_pretrained(model_info['path'])
    model_config = AutoConfig.from_pretrained(model_info['path'])
    
    if hasattr(model_config, 'quantization_config') and model_config.quantization_config:
        qm = model_config.quantization_config.get('quant_method', 'unknown')
        print(f"[OK] Pre-quantized: {qm}")
        model = AutoModelForCausalLM.from_pretrained(
            model_info['path'],
            device_map="auto",
            attn_implementation="sdpa"
        )
    else:
        print("[OK] Using BitsAndBytes 4bit")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_info['path'],
            quantization_config=bnb_config,
            device_map="auto",
            attn_implementation="sdpa"
        )
    
    load_time = time.time() - start_time
    allocated, reserved = get_gpu_memory()
    
    print(f"Load time: {load_time:.2f} s")
    print(f"VRAM: {allocated:.2f} GB (alloc), {reserved:.2f} GB (reserved)")
    
    return model, tokenizer, load_time, allocated


def test_generation(model, tokenizer, run_id=1):
    messages = [{"role": "user", "content": TEST_PROMPT}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    # Warmup
    if run_id == 1:
        print("  Warming up...")
        with torch.no_grad():
            _ = model.generate(**inputs, max_new_tokens=10, do_sample=False)
    
    print(f"  Run {run_id}...", end=" ", flush=True)
    
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
    
    print(f"done!")
    print(f"    Tokens: {generated_tokens}")
    print(f"    Time:   {total_time:.2f} s")
    print(f"    Speed:  {tokens_per_sec:.1f} tokens/s")
    print(f"    Output: {response[:60]}...")
    
    return {
        'generated_tokens': generated_tokens,
        'total_time': total_time,
        'tokens_per_sec': tokens_per_sec,
        'response': response
    }


def unload_model(model, tokenizer):
    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    print("\n[OK] Model unloaded, VRAM freed")


def main():
    print("="*60)
    print("Qwen2.5 Speed Benchmark: 3B vs 7B")
    print("="*60)
    print(f"Prompt: {TEST_PROMPT}")
    print(f"Max tokens: {MAX_NEW_TOKENS}")
    print(f"Runs per model: {NUM_RUNS}")
    
    results = {}
    
    # Test 3B
    try:
        model_3b, tokenizer_3b, load_time_3b, memory_3b = load_model("3B")
        results['3B'] = {
            'load_time': load_time_3b,
            'memory': memory_3b,
            'runs': []
        }
        for i in range(1, NUM_RUNS + 1):
            result = test_generation(model_3b, tokenizer_3b, i)
            results['3B']['runs'].append(result)
        unload_model(model_3b, tokenizer_3b)
    except Exception as e:
        print(f"[FAIL] 3B test error: {e}")
        results['3B'] = None
    
    # Test 7B
    try:
        model_7b, tokenizer_7b, load_time_7b, memory_7b = load_model("7B")
        results['7B'] = {
            'load_time': load_time_7b,
            'memory': memory_7b,
            'runs': []
        }
        for i in range(1, NUM_RUNS + 1):
            result = test_generation(model_7b, tokenizer_7b, i)
            results['7B']['runs'].append(result)
        unload_model(model_7b, tokenizer_7b)
    except Exception as e:
        print(f"[FAIL] 7B test error: {e}")
        results['7B'] = None
    
    # Results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    if results['3B'] and results['7B']:
        avg_speed_3b = sum(r['tokens_per_sec'] for r in results['3B']['runs']) / NUM_RUNS
        avg_time_3b = sum(r['total_time'] for r in results['3B']['runs']) / NUM_RUNS
        
        avg_speed_7b = sum(r['tokens_per_sec'] for r in results['7B']['runs']) / NUM_RUNS
        avg_time_7b = sum(r['total_time'] for r in results['7B']['runs']) / NUM_RUNS
        
        print(f"\n{'Model':<20} {'Load(s)':<12} {'VRAM(GB)':<12} {'Speed(tok/s)':<14} {'Time(s)':<12}")
        print("-"*70)
        print(f"{'3B (BnB-Int4)':<20} {results['3B']['load_time']:<12.2f} {results['3B']['memory']:<12.2f} {avg_speed_3b:<14.1f} {avg_time_3b:<12.2f}")
        print(f"{'7B (GPTQ-Int4)':<20} {results['7B']['load_time']:<12.2f} {results['7B']['memory']:<12.2f} {avg_speed_7b:<14.1f} {avg_time_7b:<12.2f}")
        print("-"*70)
        
        speed_ratio = avg_speed_3b / avg_speed_7b if avg_speed_7b > 0 else 0
        print(f"\nConclusion:")
        print(f"  3B is {speed_ratio:.1f}x faster than 7B")
        print(f"  7B is {(speed_ratio - 1) * 100:.0f}% slower")
        print(f"  7B uses {results['7B']['memory'] - results['3B']['memory']:.2f} GB more VRAM")
    
    print("\n" + "="*60)
    print("Benchmark done!")
    print("="*60)


if __name__ == "__main__":
    main()
