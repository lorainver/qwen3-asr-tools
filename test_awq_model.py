"""
测试 AWQ 量化模型加载
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig

model_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-3B-Instruct-AWQ"

print(f"Test model: {model_path}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print()

# 检查模型配置
print("1. Check model config...")
config = AutoConfig.from_pretrained(model_path)
print(f"   Model type: {config.model_type}")
print(f"   Has quantization_config: {hasattr(config, 'quantization_config')}")
if hasattr(config, 'quantization_config') and config.quantization_config:
    print(f"   Quantization method: {config.quantization_config.quant_method if hasattr(config.quantization_config, 'quant_method') else 'AWQ'}")
print()

# 加载 tokenizer
print("2. Loading Tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_path)
print("   [OK] Tokenizer loaded")
print()

# 加载模型
print("3. Loading Model...")
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    torch_dtype=torch.float16
)
print("   [OK] Model loaded")
print(f"   Model device: {model.device}")
print()

# 测试推理
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
        max_new_tokens=100,
        do_sample=True,
        temperature=0.7
    )

response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
print(f"   [OK] Inference success")
print(f"   Response: {response}")
print()

# 显存使用
print("5. Memory usage:")
print(f"   Allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB")
print(f"   Reserved: {torch.cuda.memory_reserved() / 1024**2:.1f} MB")
print()

print("[SUCCESS] AWQ model works correctly!")