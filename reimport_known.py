"""
使用已知群名重新导出和导入所有9个群聊
"""
import sys, os, json, time, subprocess
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['OLLAMA_MODELS'] = 'D:\\ollama\\models'

from pathlib import Path
from knowledge_store import init_knowledge_base, index_document, get_vectorstore, DOCS_PATH

# 0. 初始化
print("=== 步骤0: 初始化 ===")
init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 清空
all_ids = vs.collection.get(limit=10000)
if all_ids['ids']:
    vs.collection.delete(ids=all_ids['ids'])
index_file = DOCS_PATH / 'index.json'
if index_file.exists():
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
print(f"KB 清空: {len(vs.collection.get(limit=10000)['ids'])} chunks")

# 目标群聊（已知名称）
TARGET_GROUPS = [
    '南岸中小学二手闲置',
    '米妈家长圈闲置2群',
    '4-5年级上岸政策活动群',
    '重庆大学MBA总群(2)',
    '金佛山-良瑜业主3群',
    '果妈思维小初宝藏群（米妈定制）',
    '💪信竞家长交流群',
    '数学竞赛家长交流群（小雅）',
    '欣怡宝贝外贸童装1⃣ 群',  # 注意群前有空格
]

wechat_dir = Path("D:/qwen3-asr/knowledge_base/wechat")
wechat_dir.mkdir(parents=True, exist_ok=True)

# 导入转换器
from wechat_cli_importer import WeChatCliImporter

total_chunks = 0
for i, group_name in enumerate(TARGET_GROUPS):
    safe_name = group_name.replace('/', '_').replace('\\', '_')[:30]
    raw_file = wechat_dir / f"{safe_name}_raw.md"
    std_file = wechat_dir / f"{safe_name}_raw.standard.md"
    
    # 1. 导出
    print(f"\n[{i+1}/{len(TARGET_GROUPS)}] 导出: {group_name}")
    cmd = ['wechat-cli', 'export', group_name, '--start-time', '2026-01-09']
    try:
        r = subprocess.run(cmd, capture_output=True, text=False, timeout=60)
        stdout_text = r.stdout.decode('utf-8', errors='replace')
        
        if r.returncode != 0:
            stderr_text = r.stderr.decode('utf-8', errors='replace')
            print(f"  导出失败 (rc={r.returncode}): {stderr_text[:200]}")
            continue
        
        # 保存原始
        with open(raw_file, 'w', encoding='utf-8') as f:
            f.write(stdout_text)
        lines = stdout_text.count('\n')
        print(f"  原始文件: {raw_file.name} ({lines} 行)")
        
        # 2. 转换格式
        importer = WeChatCliImporter()
        std_output = importer.convert_to_standard_format(str(raw_file))
        
        # 3. 导入 KB
        result = index_document(str(std_file), category='微信聊天记录_wechat-cli-20260109')
        print(f"  doc_id={result['doc_id'][:8]}, chunks={result['chunk_count']}")
        total_chunks += result['chunk_count']
        
        # 4. 验证
        peek_ids = vs.collection.peek(limit=10000)['ids']
        print(f"  KB peek: {len(peek_ids)} chunks")
        
    except subprocess.TimeoutExpired:
        print(f"  超时!")
    except Exception as e:
        print(f"  错误: {e}")

print(f"\n=== 最终状态 ===")
peek_ids = vs.collection.peek(limit=10000)['ids']
print(f"KB peek: {len(peek_ids)} chunks (total imported: {total_chunks})")

# 统计
all_results = vs.collection.get(limit=10000, include=['metadatas'])
from collections import Counter
doc_counts = Counter()
doc_names = {}
for m in all_results['metadatas']:
    did = m.get('doc_id', '?')
    doc_counts[did] += 1
    doc_names[did] = m.get('filename', '?')

print(f"\n文档 ({len(doc_counts)} 个):")
for did, cnt in sorted(doc_counts.items()):
    print(f"  {did[:8]}: {cnt} - {doc_names[did]}")
