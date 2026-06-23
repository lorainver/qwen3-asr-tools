"""直接测试 ChromaDB add 是否工作"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

import chromadb
from chromadb.config import Settings
from pathlib import Path

# 连接到同一个 ChromaDB
CHROMA_PATH = Path("D:/qwen3-asr/knowledge_base/chroma_db")
client = chromadb.PersistentClient(
    path=str(CHROMA_PATH),
    settings=Settings(anonymized_telemetry=False)
)
collection = client.get_or_create_collection(
    name="knowledge_base",
    metadata={"description": "qwen3-asr 知识库"}
)

print(f"Collection count before: {collection.count()}")

# 尝试直接添加一条记录
test_id = "debug_test_001"
test_doc = "这是一个测试文档内容"
test_meta = {"filename": "test.md", "doc_id": "test_001", "category": "test", "source": "debug"}

try:
    # 先获取 embedding
    from knowledge_store import init_knowledge_base, get_embedder
    init_knowledge_base(summarizer=None)
    emb = get_embedder()
    emb_test = emb.embed_texts([test_doc])
    print(f"Embedding dim: {len(emb_test[0])}")
    
    print(f"Adding test record...")
    collection.add(
        ids=[test_id],
        embeddings=emb_test,
        documents=[test_doc],
        metadatas=[test_meta]
    )
    print(f"Add completed without error")
    print(f"Collection count after: {collection.count()}")
    
    # 查一下
    r = collection.get(ids=[test_id])
    print(f"get([test_id]): {r['ids']}")
    
except Exception as e:
    print(f"EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
