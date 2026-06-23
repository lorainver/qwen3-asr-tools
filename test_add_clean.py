"""清理测试数据，然后重新测试"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 1. 删除测试记录
print("1. 删除测试记录...")
all_ids = vs.collection.get(limit=10000)
test_ids = [i for i in all_ids['ids'] if 'debug' in i or i.startswith('wechat_c')]
print(f"   要删除的 IDs: {test_ids[:10]}...")

if test_ids:
    vs.collection.delete(ids=test_ids)
    print(f"   删除后 count: {vs.collection.count()}")

# 2. 现在测试 add
print("\n2. 测试 vs.collection.add...")
count_before = vs.collection.count()
print(f"   count before: {count_before}")

# 添加一条测试记录
from knowledge_store import get_embedder
emb = get_embedder()
emb_test = emb.embed_texts(["测试文档内容"])
print(f"   embedding dim: {len(emb_test[0])}")

vs.collection.add(
    ids=["test_fresh_001"],
    embeddings=emb_test,
    documents=["测试文档内容"],
    metadatas=[{"filename": "test.md", "doc_id": "test_fresh", "category": "test"}]
)

count_after = vs.collection.count()
print(f"   count after: {count_after}, delta: {count_after - count_before}")

# 3. 检查 test_fresh_001 是否存在
r = vs.collection.get(ids=["test_fresh_001"])
print(f"   test_fresh_001 exists: {len(r['ids']) > 0}")

# 4. 列出前10个 IDs
peek = vs.collection.peek(limit=10)
print(f"   peek(10) ids: {peek['ids']}")
