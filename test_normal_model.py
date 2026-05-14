"""
Test normal model with BitsAndBytes quantization
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

model_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-3B-Instruct"

print(f"Test model: {model_path}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print()

# Load tokenizer
print("1. Loading Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_path)
print("   [OK] Tokenizer loaded")
print()

# Load model with BitsAndBytes 4-bit quantization
print("2. Loading Model with BitsAndBytes 4-bit...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4"
)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.float16
)
print("   [OK] Model loaded")
print(f"   Model device: {model.device}")
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

print("[SUCCESS] Normal model with BitsAndBytes works!")
