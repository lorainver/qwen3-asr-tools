"""深入调试 index_document 的问题"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, index_document, get_vectorstore
import knowledge_store

# 1. 确认 _vectorstore 状态
print(f"1. _vectorstore before init: {knowledge_store._vectorstore}")

# 2. 初始化
init_knowledge_base(summarizer=None)
print(f"2. _vectorstore after init: {knowledge_store._vectorstore}")

# 3. 导入前查 KB
vs = get_vectorstore()
before = vs.collection.count()
print(f"3. KB count before: {before}")

# 4. 直接查 ChromaDB collection
results_before = vs.collection.get(include=['metadatas'])
doc_ids_before = set(m.get('doc_id', '?') for m in results_before['metadatas'])
print(f"4. Doc IDs before: {sorted(doc_ids_before)}")

# 5. 打印 index_document 的关键步骤
import logging
logging.basicConfig(level=logging.INFO)

print("\n5. 开始 index_document...")
result = index_document(
    r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md",
    category="微信聊天记录_wechat-cli-20260109"
)
print(f"6. index_document result: {result}")

# 6. 检查是否写入
vs2 = get_vectorstore()
after = vs2.collection.count()
print(f"7. KB count after: {after}")

results_after = vs2.collection.get(include=['metadatas'])
doc_ids_after = set(m.get('doc_id', '?') for m in results_after['metadatas'])
print(f"8. Doc IDs after: {sorted(doc_ids_after)}")

new_ids = doc_ids_after - doc_ids_before
print(f"9. NEW doc IDs: {new_ids}")
