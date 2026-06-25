import sqlite3, os, glob

conn = sqlite3.connect('D:/qwen3-asr/knowledge_base/wechat_chat_records.db')
cursor = conn.cursor()

# 1. 查看 source 字段
print("=== Source field samples ===")
cursor.execute("SELECT content, source FROM messages WHERE content LIKE '%[图片]%' LIMIT 2")
for r in cursor.fetchall():
    print("Content:", (r[0] or "")[:80])
    print("Source:", (r[1] or "")[:200])
    print("---")

# 2. 检查 wechat-cli 数据目录是否有图片文件
print("\n=== Checking for image files in wechat data ===")
# 常见的微信数据存储路径
paths_to_check = [
    os.path.expanduser("~\\Documents\\WeChat Files"),
    os.path.expanduser("~\\AppData\\Roaming\\Tencent\\WeChat"),
    "D:\\WeChatFiles",
]
for p in paths_to_check:
    if os.path.exists(p):
        print(f"Found: {p}")
        # 查找图片文件夹
        for root, dirs, files in os.walk(p):
            depth = root.replace(p, "").count(os.sep)
            if depth > 3:
                continue
            if any(d in dirs for d in ["Image", "image", "Images", "images", "FileStorage"]):
                for d in ["Image", "image", "Images", "images", "FileStorage"]:
                    if d in dirs:
                        img_dir = os.path.join(root, d)
                        count = sum(1 for _ in os.listdir(img_dir)) if os.path.isdir(img_dir) else 0
                        print(f"  {img_dir} ({count} files)")

# 3. 检查 wechat-cli 配置中的数据路径
print("\n=== Checking wechat-cli config ===")
config_paths = [
    os.path.expanduser("~\\.wechat-cli\\config.json"),
    os.path.expanduser("~\\.config\\wechat-cli\\config.json"),
]
for cp in config_paths:
    if os.path.exists(cp):
        import json
        with open(cp, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            print(f"Config at {cp}:")
            for k, v in cfg.items():
                if 'path' in k.lower() or 'dir' in k.lower() or 'data' in k.lower() or 'file' in k.lower():
                    print(f"  {k}: {v}")

conn.close()
