"""
清理 + 完整重新导入所有 9 个群聊
"""
import sys, os, json, time, subprocess, shutil
from pathlib import Path
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

from knowledge_store import init_knowledge_base, index_document, get_vectorstore, DOCS_PATH

# 0. 初始化
print("=== 步骤0: 初始化 ===")
init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 清理
all_ids = vs.collection.get(limit=10000)
if all_ids['ids']:
    vs.collection.delete(ids=all_ids['ids'])
index_file = DOCS_PATH / 'index.json'
if index_file.exists():
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump([], f, ensure_ascii=False, indent=2)
print(f"KB 清空: peek()={len(vs.collection.peek(limit=10000)['ids'])} chunks")

# 导出所有群聊
print("\n=== 步骤1: 导出所有群聊 ===")
# 获取群聊列表
result = subprocess.run(
    ['wechat-cli', 'sessions', '--limit', '40'],
    capture_output=True, text=True,
    encoding='utf-8', errors='replace'
)
lines = result.stdout.strip().split('\n')

groups = []
for line in lines:
    if '|' in line and not line.startswith('===') and 'pid' not in line[:10].lower():
        parts = line.split('|')
        if len(parts) >= 2:
            pid = parts[0].strip()
            name = parts[1].strip()
            if pid.isdigit() and name:
                groups.append((pid, name))

# 排序（时间顺序）
groups = sorted(groups, key=lambda x: x[0])
print(f"找到 {len(groups)} 个群聊")

# 9 个已知群聊（排除盒马）
target_groups = {
    '9258': '南岸中小学二手闲置',
    '9159': '米妈家长圈闲置2群',
    '9191': '4-5年级上岸政策活动群',
    '9233': '重庆大学MBA总群(2)',
    '9234': '金佛山-良瑜业主3群',
    '9260': '果妈思维小初宝藏群（米妈定制）',
    '9268': '💪信竞家长交流群',
    '9272': '数学竞赛家长交流群（小雅）',
    '9268b': '欣怡宝贝外贸童装1⃣群',
}

# 用欣怡 pid
target_pids = ['9258', '9191', '9233', '9234', '9159', '9260', '9268', '9272', '9280']
target_names = {}
for pid, name in groups:
    if pid in target_pids:
        target_names[pid] = name

print(f"目标群聊: {list(target_names.keys())}")

# 2. 导出并导入
print("\n=== 步骤2: 导出 + 导入 ===")
wechat_dir = Path("D:/qwen3-asr/knowledge_base/wechat")
wechat_dir.mkdir(parents=True, exist_ok=True)

for pid in target_pids:
    name = target_names.get(pid, f'群{pid}')
    safe_name = name.replace('/', '_').replace('\\', '_')[:30]
    out_file = wechat_dir / f"{safe_name}_raw.md"
    
    # 导出
    print(f"\n导出 [{pid}] {name}...")
    cmd = ['wechat-cli', 'export', '--pid', pid, '--start-time', '2026-01-09']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        if r.returncode != 0:
            print(f"  导出失败: {r.stderr[:200]}")
            continue
        
        # 保存
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(r.stdout)
        lines_written = len(r.stdout.splitlines())
        print(f"  已保存: {out_file} ({lines_written} 行)")
        
        # 转换格式
        from wechat_cli_importer import WeChatCliImporter
        importer = WeChatCliImporter()
        standard_file = out_file.with_name(out_file.stem + '_raw.standard.md')
        importer.convert_to_standard_format(str(out_file), str(standard_file))
        print(f"  转换格式: {standard_file.name}")
        
        # 导入 KB
        print(f"  导入 KB...", end='', flush=True)
        result = index_document(str(standard_file), category='微信聊天记录_wechat-cli-20260109')
        print(f" doc_id={result['doc_id'][:8]}, chunks={result['chunk_count']}")
        
        # 验证 peek
        peek_ids = vs.collection.peek(limit=10000)['ids']
        print(f"  KB peek: {len(peek_ids)} chunks")
        
    except Exception as e:
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()

# 最终状态
print("\n=== 最终状态 ===")
peek_ids = vs.collection.peek(limit=10000)['ids']
print(f"KB peek: {len(peek_ids)} chunks")
print(f"KB peek (前20 IDs): {peek_ids[:20]}")

# 统计 doc_ids
all_results = vs.collection.get(limit=10000, include=['metadatas'])
from collections import Counter
doc_counts = Counter()
doc_names = {}
for m in all_results['metadatas']:
    did = m.get('doc_id', '?')
    doc_counts[did] += 1
    doc_names[did] = m.get('filename', '?')

print(f"\n文档统计 ({len(doc_counts)} 个文档):")
for did, cnt in sorted(doc_counts.items()):
    print(f"  {did[:8]}: {cnt} chunks - {doc_names[did]}")
print(f"\n总计: {sum(doc_counts.values())} chunks")
