import sys
import os

# 导入 LongTextSummarizer
from summarizer import LongTextSummarizer

def test_mimo():
    print("=== 初始化 LongTextSummarizer ===")
    summarizer = LongTextSummarizer()
    
    # 模拟切换到 mimo-v2.5-pro
    model_id = "mimo-v2.5-pro"
    print(f"\n=== 切换到模型: {model_id} ===")
    success = summarizer.switch_model(model_id)
    if not success:
        print("[-] 切换模型失败，请检查 config.yaml 中是否正确配置了该模型！")
        return
        
    print(f"[+] 成功切换到 {model_id}！")
    print(f"当前模型信息: {summarizer.get_current_model()}")
    print(f"是否为远程模型: {summarizer.is_remote}")
    print(f"API 地址: {summarizer.api_url}")
    
    # 检测 api_key
    model_info = summarizer.available_models.get(model_id, {})
    api_key = model_info.get("api_key")
    print(f"配置的 API Key: {api_key}")
    
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("\n[!] 提示: 检测到 API Key 为空或占位符。本次测试将只验证切换逻辑与请求格式构建，实际请求将因鉴权失败返回 401。")
        
    # 测试消息
    messages = [
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]
    
    print("\n=== 开始流式对话测试 ===")
    try:
        # 执行流式生成
        for token in summarizer.chat_stream(messages):
            try:
                print(token, end="", flush=True)
            except UnicodeEncodeError:
                # 兼容 Windows CMD 编码限制
                safe_token = token.encode('gbk', errors='replace').decode('gbk')
                print(safe_token, end="", flush=True)
        print("\n\n[+] 流式对话测试完成！")
    except Exception as e:
        print(f"\n[-] 请求执行失败: {e}")

if __name__ == "__main__":
    test_mimo()
