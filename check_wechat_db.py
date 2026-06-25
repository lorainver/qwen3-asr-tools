import sqlite3, os

# 检查原始微信数据库
db_path = r"D:\xwechat_files\loeainve_7aee\db_storage"
print("=== Scanning db_storage ===")
for f in os.listdir(db_path):
    fp = os.path.join(db_path, f)
    if os.path.isfile(fp) and f.endswith('.db'):
        print(f"\nDatabase: {f} ({os.path.getsize(fp)} bytes)")
        try:
            conn = sqlite3.connect(fp)
            cursor = conn.cursor()
            # 列出所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            print(f"  Tables: {tables}")
            
            # 查找可能包含图片信息的表
            for t in tables:
                if any(kw in t.lower() for kw in ['msg', 'image', 'img', 'media', 'attach']):
                    try:
                        cursor.execute(f"SELECT * FROM {t} LIMIT 1")
                        cols = [d[0] for d in cursor.description]
                        row = cursor.fetchone()
                        if row:
                            print(f"  Table {t}: columns={cols[:10]}")
                    except:
                        pass
            conn.close()
        except Exception as e:
            print(f"  Error: {e}")

# 也检查 msg/file 目录
file_dir = r"D:\xwechat_files\loeainve_7aee\msg\file"
if os.path.exists(file_dir):
    print(f"\n=== Files in msg/file ({len(os.listdir(file_dir))} items) ===")
    for f in os.listdir(file_dir)[:5]:
        fp = os.path.join(file_dir, f)
        if os.path.isdir(fp):
            subfiles = os.listdir(fp)
            print(f"  {f}/: {len(subfiles)} items")
            if subfiles:
                sfp = os.path.join(fp, subfiles[0])
                if os.path.isfile(sfp):
                    with open(sfp, 'rb') as fh:
                        hdr = fh.read(4)
                        print(f"    {subfiles[0]}: header={hdr.hex()}, size={os.path.getsize(sfp)}")
