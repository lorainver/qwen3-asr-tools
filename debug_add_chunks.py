"""最细粒度的 debug：检查 add_chunks 是否真的写入了"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Patch add_chunks to add debug output
import knowledge_store
original_add = knowledge_store.VectorStore.add_chunks

def debug_add_chunks(self, chunks, embeddings):
    count_before = self.collection.count()
    print(f"DEBUG: count_before add_chunks = {count_before}")
    print(f"DEBUG: adding {len(chunks)} chunks, first chunk_id = {chunks[0].chunk_id if chunks else 'NONE'}")
    print(f"DEBUG: first embedding dim = {len(embeddings[0]) if embeddings else 'NONE'}")
    
    try:
        original_add(self, chunks, embeddings)
        count_after = self.collection.count()
        print(f"DEBUG: count_after add_chunks = {count_after}")
        print(f"DEBUG: delta = {count_after - count_before}")
    except Exception as e:
        print(f"DEBUG: EXCEPTION in add_chunks: {e}")
        import traceback
        traceback.print_exc()

knowledge_store.VectorStore.add_chunks = debug_add_chunks

# Now run the full test
from knowledge_store import init_knowledge_base, index_document, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

print(f"\nInitial KB count: {vs.collection.count()}")

# Get first embedding to test Ollama
from knowledge_store import get_embedder
emb = get_embedder()
test_emb = emb.embed_texts(["测试"])
print(f"Test embedding dim: {len(test_emb[0])}")

print("\nCalling index_document...")
result = index_document(
    r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md",
    category="微信聊天记录_wechat-cli-20260109"
)

print(f"\nFinal KB count: {vs.collection.count()}")
print(f"Result: {result}")
