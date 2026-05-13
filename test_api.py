import requests
import json

# 配置信息
# API_URL = "http://127.0.0.1:8001/v1/chat/completions"
# API_URL = "http://192.168.0.2:8001/v1/chat/completions"
API_URL = "http://116.168.23.146:28001/v1/chat/completions"

# 自动获取当前服务器的状态（当前模型和可用列表）
def get_server_status():
    try:
        base_url = API_URL.split('/v1/')[0]
        resp = requests.get(f"{base_url}/api/models", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {"current": {"id": "qwen-general"}, "available": []}

def test_chat():
    status = get_server_status()
    current_model = status.get('current', {}).get('id', 'qwen-general')
    available_models = [m['id'] for m in status.get('available', [])]
    
    print(f"--- 服务器状态 ---")
    print(f"✅ 当前活跃模型: {current_model}")
    if available_models:
        print(f"📜 所有可用模型: {', '.join(available_models)}")
    print(f"------------------\n")

    payload = {
        "model": current_model,
        "messages": [
            {"role": "system", "content": "你是一个幽默的助手。"},
            {"role": "user", "content": "请用三句话介绍一下你自己，并告诉我你现在跑在哪种显卡上？"}
        ],
        "stream": True  # 开启流式传输，体验更好
    }

    print(f"--- 正在通过 OpenAI 接口请求模型: {current_model} ---")
    try:
        response = requests.post(API_URL, json=payload, stream=True, timeout=10)
        response.raise_for_status()
        print("AI 回复: ", end="", flush=True)

        for line in response.iter_lines():
            if line:
                # 去掉 'data: ' 前缀
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data_str = line_text[6:]
                    try:
                        data_json = json.loads(data_str)
                        content = data_json['choices'][0]['delta'].get('content', '')
                        print(content, end="", flush=True)
                    except json.JSONDecodeError as e:
                        print(f"JSON 解析错误: {e}", end="", flush=True)
                else:
                    print(line.decode('utf-8'), end="", flush=True)

        print("\n\n--- 测试完成 ---")
    except requests.exceptions.Timeout:
        print("\n❌ 超时：服务器 10 秒没有响应！")
        print("请检查：1. 服务是否启动  2. 地址和端口是否正确")
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接失败：无法连接到服务器！")
        print("请检查：192.168.0.2:8001 服务是否运行")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("请检查 AI Worker (8001 端口) 是否正在运行？")

if __name__ == "__main__":
    test_chat()