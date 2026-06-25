"""批量导出最近更新的前10个群聊到知识库"""
import subprocess
import json
import sys
import os
import time

sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# wechat-cli sessions 输出的群聊（已按时间排序）
GROUPS = [
    {"name": " 盒马🍃端午节😋- 云领店18群", "username": "45439314624@chatroom"},
    {"name": "米妈家长圈闲置2群", "username": "47787114793@chatroom"},
    {"name": "南岸中小学二手闲置", "username": "50439274850@chatroom"},
    {"name": "4-5年级上岸政策活动群", "username": "57681216182@chatroom"},
    {"name": "重庆大学MBA总群(2)", "username": "2043010637@chatroom"},
    {"name": "金佛山-良瑜业主3群", "username": "45118286738@chatroom"},
    {"name": "欣怡宝贝外贸童装1⃣ 群", "username": "22233340697@chatroom"},
    {"name": "果妈思维小初宝藏群（米妈定制）", "username": "43631244298@chatroom"},
    {"name": "💪信竞家长交流群", "username": "53243225982@chatroom"},
    {"name": "数学竞赛家长交流群（小雅）", "username": "53098535294@chatroom"},
]

OUTPUT_DIR = r"D:\qwen3-asr\knowledge_base\wechat"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 测试模式：只处理指定群聊（None = 处理全部）
TEST_GROUP = None  # 设为 None 处理全部

def export_group(group_name, username, start_time="2026-01-09"):
    """用 wechat-cli export 导出群聊消息（从指定日期开始）"""
    safe_name = group_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
    out_file = os.path.join(OUTPUT_DIR, f"{safe_name}_raw.md")
    
    cmd = [
        'wechat-cli',
        'export',
        group_name.strip(),
        '--format', 'markdown',
        '--start-time', start_time,
        '--output', out_file
    ]
    
    print(f"📤 导出（从 {start_time} 开始）: {group_name}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding='utf-8',
            timeout=300, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        if result.returncode == 0 and os.path.exists(out_file):
            size = os.path.getsize(out_file)
            # 统计消息数
            with open(out_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                msg_count = len([l for l in lines if l.startswith('- [')])
            print(f"  ✅ 成功: {size} bytes, ~{msg_count} 条消息")
            return out_file, True
        else:
            err = result.stderr[:300] if result.stderr else "unknown"
            print(f"  ❌ 失败: {err}")
            return out_file, False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return out_file, False

def convert_to_standard(raw_path):
    """用 wechat_cli_importer 转换为标准格式"""
    from wechat_cli_importer import WeChatCliImporter
    importer = WeChatCliImporter(output_dir=r"D:\qwen3-asr\knowledge_base\wechat")
    
    try:
        std_path = importer.convert_to_standard_format(raw_path)
        size = os.path.getsize(std_path)
        print(f"  🔄 转换: {size} bytes → {os.path.basename(std_path)}")
        return std_path, True
    except Exception as e:
        print(f"  ❌ 转换失败: {e}")
        return raw_path, False

def import_to_kb(std_path, group_name, export_source="wechat-cli-20260109"):
    """导入知识库，添加 export_source 元数据便于今后合并"""
    from knowledge_store import init_knowledge_base, index_document, delete_by_filename
    
    # 只初始化一次
    if not hasattr(import_to_kb, '_initialized'):
        init_knowledge_base(summarizer=None)
        import_to_kb._initialized = True
    
    category = f"微信聊天记录_{export_source}"
    
    try:
        # ✅ 去重：只删除同来源（category）的旧数据，避免误删其他来源
        deleted = delete_by_filename(group_name, category=category)
        if deleted > 0:
            print(f"  🗑️ 删除旧数据: {deleted} chunks (category={category})")
        
        # 通过 category 参数传递 export_source 信息
        result = index_document(std_path, category=category)
        print(f"  📚 导入KB: {result['chunk_count']} chunks, doc_id={result['doc_id']}")
        return result
    except Exception as e:
        print(f"  ❌ 导入KB失败: {e}")
        return None

# 主流程
if __name__ == "__main__":
    results = []
    
    # 如果设置了 TEST_GROUP，只处理该群
    if TEST_GROUP:
        groups_to_process = [g for g in GROUPS if g["name"].strip() == TEST_GROUP.strip()]
        if not groups_to_process:
            print(f"❌ 未找到测试群: {TEST_GROUP}")
            sys.exit(1)
        print(f"🧪 测试模式：仅处理 {TEST_GROUP}")
    else:
        groups_to_process = GROUPS
    
    for g in groups_to_process:
        name = g["name"]
        print(f"\n{'='*60}")
        print(f"处理: {name}")
        
        # 1. 导出（从2026-01-09开始，不限制条数）
        raw_path, ok = export_group(name, g["username"], start_time="2026-01-09")
        if not ok:
            continue
        time.sleep(2)  # 避免过快
        
        # 2. 转换
        std_path, ok = convert_to_standard(raw_path)
        if not ok:
            continue
        
        # 3. 导入知识库（标记来源便于合并）
        result = import_to_kb(std_path, name, export_source="wechat-cli-20260109")
        
        # 4. 同步导入 SQLite 结构化数据库
        try:
            from wechat_db import wechat_db
            db_ok = wechat_db.import_markdown_file(raw_path)
            if db_ok:
                print(f"  📊 导入 SQLite 数据库成功")
            else:
                print(f"  ❌ 导入 SQLite 数据库失败")
        except Exception as db_err:
            print(f"  ❌ 导入 SQLite 数据库发生异常: {db_err}")
            
        if result:
            results.append({"group": name, **result})
    
    print(f"\n{'='*60}")
    print(f"📊 导入完成: {len(results)}/{len(GROUPS)} 个群聊")
    for r in results:
        print(f"  - {r['group']}: {r['chunk_count']} chunks")
