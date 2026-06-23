"""清除测试数据并重新测试导入"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, get_embedder, index_document

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 清除所有旧数据
try:
    all_data = vs.collection.get()
    if all_data and all_data['ids']:
        print(f"清除旧数据: {len(all_data['ids'])} 块")
        vs.collection.delete(ids=all_data['ids'])
except Exception as e:
    print(f"清除失败: {e}")

print(f"清除后块数: {vs.count()}")

# 重新导入
print("\n--- 重新导入测试 ---")
result = index_document(
    "D:/qwen3-asr/knowledge_base/wechat/信竞家长交流群_测试.standard.md",
    category="微信聊天记录"
)
print(f"doc_id: {result['doc_id']}")
print(f"chunk_count: {result['chunk_count']}")

# 测试搜索
print("\n--- 测试搜索 ---")
embedder = get_embedder()
for query in ["CSP初赛", "高考数学", "英语口语", "空洞骑士"]:
    emb = embedder.embed_texts([query])[0]
    hits = vs.search(emb, top_k=2)
    print(f"\n🔍 '{query}' → {len(hits)} 条结果:")
    for i, h in enumerate(hits, 1):
        print(f"  {i}. [{h.metadata.get('timestamp', '?')}] {h.metadata.get('speaker', '?')} ({h.metadata.get('msg_count', '?')}条消息)")
        print(f"     {h.text[:80].replace(chr(10), ' ')}...")
