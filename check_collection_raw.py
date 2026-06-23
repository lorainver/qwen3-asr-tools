"""直接查询 ChromaDB collection 原始数据"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 直接查 collection 原始数据
results = vs.collection.get(include=["metadatas"])

print(f"ChromaDB 原始记录数: {len(results['ids'])}")
print()

# 按 filename 分组统计
files = {}
for meta in results['metadatas']:
    fn = meta.get('filename', '?')
    if fn not in files:
        files[fn] = {'count': 0, 'category': meta.get('category', '?'), 'doc_ids': set()}
    files[fn]['count'] += 1
    files[fn]['doc_ids'].add(meta.get('doc_id', '?'))

print(f"不同文件数: {len(files)}")
for fn, info in sorted(files.items()):
    print(f"  {fn}: {info['count']} chunks, category={info['category']}")
    print(f"    doc_ids: {info['doc_ids']}")
