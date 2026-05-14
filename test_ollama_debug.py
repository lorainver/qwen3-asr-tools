import requests
import time
import json

def debug_ollama(model_name="qwen2.5:3b"):
    url = "http://localhost:11434/v1/chat/completions"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "你好，请回复'连接成功'"}],
        "stream": False
    }
    
    print(f"--- Ollama 深度诊断程序 ---")
    print(f"目标模型: {model_name}")
    print(f"请求地址: {url}")
    
    start_time = time.time()
    try:
        print("\n正在发起请求（请观察显卡驱动面板，看显存是否在上涨）...")
        # 这里给 120 秒超长等待时间，彻底排除网络因素
        response = requests.post(url, json=payload, timeout=120)
        
        elapsed = time.time() - start_time
        print(f"请求结束，耗时: {elapsed:.2f} 秒")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ 诊断成功！模型回复: {content}")
        else:
            print(f"❌ 诊断失败！状态码: {response.status_code}")
            print(f"错误详情: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"🚨 严重错误: 请求在 120 秒内依然超时！")
        print("这通常意味着 Ollama 内部加载逻辑卡死了，或者磁盘 I/O 极慢。")
    except Exception as e:
        print(f"🚨 发生意外错误: {str(e)}")

if __name__ == "__main__":
    debug_ollama()
