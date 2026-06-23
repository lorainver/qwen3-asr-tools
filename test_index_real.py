"""详细测试 index_document 是否真的写入"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, index_document, get_vectorstore

# 1. 初始化并记录当前状态
init_knowledge_base(summarizer=None)
vs = get_vectorstore()
before = vs.count()
print(f"导入前 KB chunks: {before}")

# 2. 手动导入欣怡
import time
start = time.time()
result = index_document(
    r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md",
    category="微信聊天记录_wechat-cli-20260109"
)
elapsed = time.time() - start
print(f"\nindex_document 返回: {result}")
print(f"耗时: {elapsed:.1f}s")

# 3. 检查是否真的写入了
vs2 = get_vectorstore()
after = vs2.count()
print(f"\n导入后 KB chunks: {after}")
print(f"实际增加: {after - before} chunks（预期: {result['chunk_count']}）")

# 4. 直接查 collection
all_results = vs2.collection.get(include=['metadatas'])
doc_ids = set()
for m in all_results['metadatas']:
    doc_ids.add(m.get('doc_id', '?'))
print(f"\nKB 中所有 doc_ids ({len(doc_ids)}):")
for did in sorted(doc_ids):
    print(f"  {did}")
