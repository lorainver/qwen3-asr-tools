import requests
import json
import os

# 强行禁用代理，防止请求 localhost 时被转发
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

def test_ollama():
    url = "http://localhost:11434/api/tags"
    print(f"Testing connectivity to {url}...")
    try:
        resp = requests.get(url, timeout=5)
        print(f"Success! Status Code: {resp.status_code}")
        print(f"Models Available: {resp.text[:100]}")
    except Exception as e:
        print(f"FAILED to connect: {e}")
        print("\nPossible solutions:")
        print("1. Make sure Ollama is running (check taskbar).")
        print("2. Try visiting http://localhost:11434 in your browser. If it says 'Ollama is running', the service is fine.")
        print("3. Check if a VPN/Proxy is interfering with localhost requests.")

if __name__ == "__main__":
    test_ollama()
