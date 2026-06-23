"""验证 KB 最终状态"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['OLLAMA_MODELS'] = 'D:\\ollama\\models'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

from knowledge_store import init_knowledge_base, get_vectorstore, get_embedder
from collections import Counter

init_knowledge_base(summarizer=None)
vs = get_vectorstore()
emb = get_embedder()

print('=== KB 状态 ===')
print(f'count(): {vs.count()}')

all_ids = vs.collection.get(limit=10000)
print(f'get(limit=10000): {len(all_ids["ids"])}')

peek_ids = vs.collection.peek(limit=10)
print(f'peek(limit=10): {peek_ids["ids"]}')

doc_counts = Counter()
doc_names = {}
for m in all_ids['metadatas']:
    did = m.get('doc_id', '?')
    doc_counts[did] += 1
    doc_names[did] = m.get('filename', '?')

print(f'\n文档统计 ({len(doc_counts)} 个):')
for did, cnt in sorted(doc_counts.items()):
    print(f'  {did}: {cnt:3d} chunks - {doc_names[did]}')
print(f'总 chunks: {sum(doc_counts.values())}')

print('\n=== 搜索验证 ===')
for kw in ['CSP竞赛', '高考志愿', '数学竞赛', 'MBA', '金佛山', '欣怡妈', '信竞']:
    q_emb = emb.embed_query(kw)
    hits = vs.search(q_emb, top_k=3)
    if hits:
        print(f'[{kw}] -> {len(hits)} 条')
        for h in hits[:1]:
            fn = h.metadata.get('filename', '未知')
            speaker = h.metadata.get('speaker', '未知')
            print(f'  {fn} | {speaker}: {h.text[:80]}...')
