"""测试 add_chunks 的 metadata 参数是否正确"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, WeChatChunker

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 模拟 add_chunks 的逻辑
chunks = WeChatChunker(chunk_size=800, overlap=50, time_window_minutes=10).chunk_wechat_md(
    r"D:\qwen3-asr\knowledge_base\wechat\欣怡宝贝外贸童装1⃣ 群_raw.standard.md"
)

print(f"生成了 {len(chunks)} 个 chunks")

# 模拟 add_chunks 的提取
ids = [c.chunk_id for c in chunks]
texts = [c.text for c in chunks]
metadatas = [c.metadata for c in chunks]

print(f"ids[0] = {ids[0]}")
print(f"texts[0][:100] = {texts[0][:100]}")
print(f"metadatas[0] = {metadatas[0]}")
print(f"metadatas type = {type(metadatas[0])}")

# 检查 metadata 是否符合 ChromaDB 要求
print(f"\nmetadata keys: {metadatas[0].keys()}")
print(f"metadata values sample: {list(metadatas[0].values())[:5]}")

# 直接添加到 collection
from knowledge_store import get_embedder
emb = get_embedder()
embeddings = emb.embed_texts(texts[:3])
print(f"\nembeddings[0] dim = {len(embeddings[0])}")

# 测试：只添加3个
print("\n添加3个 chunks 到 collection...")
count_before = vs.collection.count()
print(f"count before: {count_before}")

try:
    vs.collection.add(
        ids=ids[:3],
        embeddings=embeddings,
        documents=texts[:3],
        metadatas=metadatas[:3]
    )
    count_after = vs.collection.count()
    print(f"count after: {count_after}, delta = {count_after - count_before}")
except Exception as e:
    print(f"EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
