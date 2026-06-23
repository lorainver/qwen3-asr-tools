"""在 index_document 过程中实时监控 collection count"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore
import chromadb

# Patch collection.count
original_count = chromadb.api.models.Collection.Collection.count
def debug_count(self):
    result = original_count(self)
    print(f"DEBUG count() called, returning: {result}")
    return result
chromadb.api.models.Collection.Collection.count = debug_count

# Patch collection.add
original_add = chromadb.api.models.Collection.Collection.add
def debug_add(self, ids, embeddings, documents, metadatas):
    print(f"DEBUG add() called with {len(ids)} ids, first id={ids[0] if ids else 'NONE'}")
    count_before = self.count()
    try:
        original_add(self, ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        count_after = self.count()
        print(f"DEBUG add() complete: {count_before} -> {count_after}, delta={count_after - count_before}")
    except Exception as e:
        print(f"DEBUG add() EXCEPTION: {e}")
        raise
chromadb.api.models.Collection.Collection.add = debug_add

# Run
init_knowledge_base(summarizer=None)
vs = get_vectorstore()

print(f"\n=== Starting index_document ===")
print(f"Count before: {vs.collection.count()}")

result = vs.index_document if hasattr(vs, 'index_document') else None

# Use module-level index_document
from knowledge_store import index_document
r = index_document(r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md", category="微信聊天记录_wechat-cli-20260109")

print(f"\n=== After index_document ===")
print(f"Count after: {vs.collection.count()}")
print(f"Result: {r}")
