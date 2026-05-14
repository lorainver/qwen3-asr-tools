import requests
import json

def test_searxng_direct():
    url = "http://192.168.31.132:8081/search"
    params = {
        "q": "python",
        "format": "json"
    }
    
    # 测试 1: 使用系统默认（可能会走代理导致失败）
    print("--- 测试 1: 使用系统默认设置 ---")
    try:
        r1 = requests.get(url, params=params, timeout=5)
        print(f"状态码: {r1.status_code}")
        print("成功连接！")
    except Exception as e:
        print(f"连接失败 (预料之中): {e}")

    # 测试 2: 强制禁用代理
    print("\n--- 测试 2: 强制禁用代理 (NO PROXY) ---")
    try:
        proxies = {"http": None, "https": None}
        r2 = requests.get(url, params=params, timeout=15, proxies=proxies)
        print(f"状态码: {r2.status_code}")
        if r2.status_code == 200:
            data = r2.json()
            print(f"成功获取结果！找到 {len(data.get('results', []))} 条记录")
    except Exception as e:
        print(f"测试 2 失败: {e}")

if __name__ == "__main__":
    test_searxng_direct()
