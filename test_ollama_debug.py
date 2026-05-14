import requests
import json
import time

def test_ollama():
    url = "http://localhost:11434/api/tags"
    print(f"--- 1. 测试基础连通性 ({url}) ---")
    try:
        resp = requests.get(url, timeout=5)
        print(f"✅ 连通性 OK, 状态码: {resp.status_code}")
        print(f"模型列表: {resp.text[:200]}...")
    except Exception as e:
        print(f"❌ 连通性失败: {e}")
        return

    print("\n--- 2. 测试模型加载 (qwen2.5:7b) ---")
    chat_url = "http://localhost:11434/v1/chat/completions"
    payload = {
        "model": "qwen2.5:7b",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False
    }
    
    start_time = time.time()
    try:
        print("正在发送请求，这可能需要几十秒（如果模型正在加载到显存）...")
        response = requests.post(chat_url, json=payload, timeout=120)
        duration = time.time() - start_time
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ 成功回复 (耗时 {duration:.2f}s):")
            print(response.json()['choices'][0]['message']['content'])
        else:
            print(f"❌ 请求失败, 响应内容: {response.text}")
    except Exception as e:
        print(f"❌ 请求发生异常: {e}")

if __name__ == "__main__":
    test_ollama()
