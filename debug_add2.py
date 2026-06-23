"""最细粒度的 debug：检查 collection.add 是否真的成功"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Patch collection.add to add debug
import knowledge_store
import chromadb

original_add = chromadb.api.models.Collection.Collection.add

def debug_add(self, ids, embeddings, documents, metadatas):
    print(f"DEBUG collection.add: {len(ids)} items, ids={ids[:3]}, first doc len={len(documents[0]) if documents else 0}")
    try:
        result = original_add(self, ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        print(f"DEBUG collection.add: SUCCESS, count now={self.count()}")
        return result
    except Exception as e:
        print(f"DEBUG collection.add: EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        raise

chromadb.api.models.Collection.Collection.add = debug_add

# Now run the full test
from knowledge_store import init_knowledge_base, index_document, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

print(f"Initial KB count: {vs.collection.count()}")

print("\nCalling index_document...")
result = index_document(
    r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md",
    category="微信聊天记录_wechat-cli-20260109"
)

print(f"\nFinal KB count: {vs.collection.count()}")
print(f"Result: {result}")
