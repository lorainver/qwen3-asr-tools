"""检查是否有重复 ID 的问题"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore
init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 检查已有 IDs 中是否有 wechat_ 前缀的
all_results = vs.collection.get(limit=1000, include=['metadatas'])
wechat_ids = []
for m in all_results['metadatas']:
    idx = m.get('chunk_index', '')
    if idx and str(idx).startswith('wechat'):
        wechat_ids.append(idx)

print(f'已有 wechat chunk IDs: {len(wechat_ids)}')
print(f'Sample: {wechat_ids[:10]}')

# 直接用 get 查 wechat_c0
r = vs.collection.get(ids=['wechat_c0', 'wechat_c1', 'wechat_c2'])
print(f'\nget([wechat_c0, wechat_c1, wechat_c2]):')
print(f'  ids returned: {r["ids"]}')
print(f'  count: {len(r["ids"])}')

# 用 peek 查全部
peek = vs.collection.peek(limit=5)
print(f'\npeek(limit=5) ids: {peek["ids"]}')
