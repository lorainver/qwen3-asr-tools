import requests
import json
import sys

# 强制设置输出编码为 UTF-8
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_ollama_thinking(model_name="gemma4:e4b", enable_think=True):
    url = "http://127.0.0.1:11434/v1/chat/completions"
    
    messages = []
    if not enable_think:
        messages.append({
            "role": "system", 
            "content": "IMPORTANT: Do not use <think> tags. Do not show your reasoning process. Provide the final answer directly."
        })
    
    messages.append({"role": "user", "content": "你好，请简单介绍一下你自己。"})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "temperature": 0.7,
        "think": enable_think
    }
    
    print(f"\n--- 测试模型: {model_name} | 深度思考: {'开启' if enable_think else '关闭'} ---")
    try:
        # 跳过系统代理
        response = requests.post(url, json=payload, timeout=60, proxies={'http': None, 'https': None})
        response.raise_for_status()
        result = response.json()
        
        message = result['choices'][0]['message']
        content = message.get('content', '')
        reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
        
        if reasoning:
            print(f"推理内容 (Reasoning):\n{reasoning}\n")
        print(f"正式回答内容 (Content):\n{content}")
        
        if reasoning or "<think>" in content:
            print("\nWARNING: 发现思考过程！")
        else:
            print("\nSUCCESS: 未发现思考过程。")
            
    except Exception as e:
        print(f"ERROR: 请求失败: {e}")

if __name__ == "__main__":
    # 1. 测试开启状态
    test_ollama_thinking(enable_think=True)
    
    print("\n" + "="*50)
    
    # 2. 测试关闭状态
    test_ollama_thinking(enable_think=False)
