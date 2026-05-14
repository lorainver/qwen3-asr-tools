import requests
import json
import os
import time

# 强行禁用代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

def test_chat():
    url = "http://localhost:11434/v1/chat/completions"
    payload = {
        "model": "qwen2.5:7b",
        "messages": [{"role": "user", "content": "Hello, who are you?"}],
        "stream": False
    }
    
    print(f"Connecting to {url}...")
    print("Asking Ollama: 'Hello, who are you?'")
    print("Wait for inference (this may take a few seconds)...")
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=60)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            print("\n[SUCCESS]")
            print(f"Time taken: {duration:.2f} seconds")
            print(f"Response: {content}")
        else:
            print(f"\n[FAILED] Status Code: {response.status_code}")
            print(f"Response body: {response.text}")
            
    except Exception as e:
        print(f"\n[ERROR] Request exception: {e}")

if __name__ == "__main__":
    test_chat()
