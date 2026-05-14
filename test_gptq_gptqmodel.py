"""
Test GPTQ model loading with gptqmodel directly (bypass optimum)
"""
import torch
from transformers import AutoTokenizer
from gptqmodel import GPTQModel

model_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"

print(f"Test model: {model_path}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print()

# Load tokenizer
print("1. Loading Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_path)
print("   [OK] Tokenizer loaded")
print()

# Load model using gptqmodel directly
print("2. Loading Model (GPTQ via gptqmodel)...")
try:
    model = GPTQModel.from_quantized(
        model_path,
        device_map="auto",
    )
    print("   [OK] Model loaded")
except Exception as e:
    print(f"   [ERROR] Failed to load model: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
print()

# Test inference
print("3. Testing inference...")
messages = [
    {"role": "user", "content": "Hello, please introduce yourself briefly."}
]
input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

print("   Generating...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=100,
        do_sample=True,
        temperature=0.7
    )

response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
print(f"   [OK] Inference success")
print(f"   Response: {response}")
print()

# Memory usage
print("4. Memory usage:")
print(f"   Allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
print(f"   Reserved: {torch.cuda.memory_reserved() / 1024**2:.1f} MB")
print()

print("[SUCCESS] GPTQ model works correctly!")
