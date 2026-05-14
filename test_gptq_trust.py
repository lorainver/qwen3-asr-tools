"""
Test GPTQ model loading directly with transformers (no optimum/gptqmodel wrapper)
"""
import os
os.environ['TORCH_COMPILE_DISABLE'] = '1'  # Disable torch compile for Windows (no Triton)

import torch
torch._dynamo.config.disable = True
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig

model_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"

print(f"Test model: {model_path}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print()

# Check model config
print("1. Check model config...")
config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
print(f"   Model type: {config.model_type}")
if hasattr(config, 'quantization_config'):
    print(f"   Quantization config: {config.quantization_config}")
print()

# Load tokenizer
print("2. Loading Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
print("   [OK] Tokenizer loaded")
print()

# Load model with trust_remote_code
print("3. Loading Model (GPTQ with trust_remote_code)...")
try:
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        trust_remote_code=True,
    )
    print("   [OK] Model loaded")
except Exception as e:
    print(f"   [ERROR] {e}")
    import traceback
    traceback.print_exc()
    exit(1)
print()

# Test inference
print("4. Testing inference...")
messages = [
    {"role": "user", "content": "Hello, please introduce yourself briefly."}
]
input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

print("   Generating...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=50,
        do_sample=True,
        temperature=0.7
    )

response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
print(f"   [OK] Inference success")
print(f"   Response: {response}")
print()

# Memory usage
print("5. Memory usage:")
print(f"   Allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
print(f"   Reserved: {torch.cuda.memory_reserved() / 1024**2:.1f} MB")
print()

print("[SUCCESS] GPTQ model works correctly!")
