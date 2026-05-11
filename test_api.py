

import requests
import json

# 配置信息
API_URL = "http://127.0.0.1:8001/v1/chat/completions"
MODEL_ID = "qwen-3b"  # 也可以换成 qwen-coder 或 qwen-1.5b

def test_chat():
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "你是一个幽默的助手。"},
            {"role": "user", "content": "请用三句话介绍一下你自己，并告诉我你现在跑在哪种显卡上？"}
        ],
        "stream": True  # 开启流式传输，体验更好
    }

    print(f"--- 正在通过 OpenAI 接口请求模型: {MODEL_ID} ---")
    
    try:
        response = requests.post(API_URL, json=payload, stream=True)
        response.raise_for_status()

        print("AI 回复: ", end="", flush=True)
        for line in response.iter_lines():
            if line:
                # 去掉 'data: ' 前缀
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_str = line_text[6:]
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data_json = json.loads(data_str)
                        content = data_json['choices'][0]['delta'].get('content', '')
                        print(content, end="", flush=True)
                    except:
                        continue
        print("\n\n--- 测试完成 ---")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("请检查 AI Worker (8001 端口) 是否正在运行？")

if __name__ == "__main__":
    test_chat()
