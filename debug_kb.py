"""详细检查 KB 中是否有欣怡文档"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 查欣怡相关的所有 chunks
results = vs.collection.get(
    where={"filename": {"$contains": "欣怡"}},
    include=["documents", "metadatas"]
)

print(f"欣怡相关 chunks: {len(results['ids']) if results else 0}")
if results and results['ids']:
    for i, doc in enumerate(results['documents'][:3]):
        print(f"  chunk {i}: {doc[:100]}...")

# 查所有 doc_ids
all_results = vs.collection.get(include=["metadatas"])
doc_ids = set()
for m in all_results['metadatas']:
    doc_ids.add(m.get('doc_id', '?'))

print(f"\n所有 doc_ids ({len(doc_ids)}):")
for did in sorted(doc_ids):
    print(f"  {did}")

# 查是否有多个 VectorStore 实例
from knowledge_store import _vectorstore, _embedding_model, _embeddings
print(f"\n_vectorstore: {_vectorstore}")
print(f"_embedding_model: {_embedding_model}")
print(f"_embeddings: {_embeddings}")

# 查 ChromaDB 持久化目录
import chromadb
print(f"\nChromaDB 持久化目录: {chromadb.persist_directory}")
client = vs._client
print(f"Client 类型: {type(client)}")
print(f"Client 设置: {client._tenant}, {client._database}")
