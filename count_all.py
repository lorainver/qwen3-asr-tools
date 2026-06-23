"""全面统计 ChromaDB collection 真实记录数"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore
init_knowledge_base(summarizer=None)
vs = get_vectorstore()

print(f"collection.count() = {vs.collection.count()}")

# peek all
all_ids = vs.collection.get(limit=10000, include=['metadatas'])
print(f"collection.get(limit=10000) 返回: {len(all_ids['ids'])} records")

# 按 doc_id 分组
from collections import Counter
doc_id_counts = Counter()
for m in all_ids['metadatas']:
    doc_id_counts[m.get('doc_id', '?')] += 1

print(f"\n按 doc_id 分组 ({len(doc_id_counts)} 个文档):")
for doc_id, count in sorted(doc_id_counts.items()):
    fn = all_ids['metadatas'][0].get('filename', '?') if all_ids['metadatas'] else '?'
    # Find filename for this doc_id
    fn = '?'
    for m in all_ids['metadatas']:
        if m.get('doc_id') == doc_id:
            fn = m.get('filename', '?')
            break
    print(f"  {doc_id}: {count} chunks - {fn}")

print(f"\n总计: {sum(doc_id_counts.values())} chunks")
