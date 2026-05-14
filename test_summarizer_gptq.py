"""Test Summarizer loading GPTQ model"""
import sys
import os
os.environ['TORCH_COMPILE_DISABLE'] = '1'
sys.path.insert(0, r'D:\qwen3-asr')

from summarizer import LongTextSummarizer

print("=" * 60)
print("Test: Summarizer + GPTQ model")
print("=" * 60)

summarizer = LongTextSummarizer()

print("\n1. Switch to GPTQ model...")
try:
    summarizer.switch_model('qwen-7b')
    print(f"   [OK] switched to: {summarizer.current_model_id}")
    print(f"   model path: {summarizer.model_path}")
except Exception as e:
    print(f"   [FAIL] switch failed: {e}")
    sys.exit(1)

print("\n2. Load model...")
try:
    summarizer._load_model()
    print("   [OK] model loaded")
except Exception as e:
    print(f"   [FAIL] load failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n3. Test inference...")
try:
    messages = [{"role": "user", "content": "Hello, introduce yourself briefly."}]
    response = summarizer.chat(messages)
    print(f"   [OK] inference success")
    print(f"   Response: {response}")
except Exception as e:
    print(f"   [FAIL] inference failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] Summarizer works with GPTQ model!")
print("=" * 60)
