"""分析知识库中两个数据源的重叠情况"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 获取所有 chunks 的元数据
results = vs.collection.get(include=["metadatas"])

# 按 category 分组
cats = {}
for meta in results['metadatas']:
    cat = meta.get('category', '未知')
    if cat not in cats:
        cats[cat] = {'count': 0, 'filenames': set()}
    cats[cat]['count'] += 1
    cats[cat]['filenames'].add(meta.get('filename', ''))

print('=== 知识库中的数据源分类 ===')
for cat, info in cats.items():
    print(f'\n📋 {cat} ({info["count"]} chunks)')
    for fn in sorted(info['filenames']):
        print(f'  - {fn}')
