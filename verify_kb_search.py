"""验证知识库搜索效果"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, get_embedder

init_knowledge_base(summarizer=None)
vs = get_vectorstore()
embedder = get_embedder()
print(f"知识库总块数: {vs.count()}")

queries = ["CSP竞赛", "高考志愿", "数学竞赛", "二手房", "MBA", "物理实验", "端午节活动"]
for q in queries:
    emb = embedder.embed_texts([q])[0]
    hits = vs.search(emb, top_k=3)
    print(f"\n🔍 '{q}' → {len(hits)} 条:")
    for h in hits:
        spk = h.metadata.get('speaker', '?')
        ts = h.metadata.get('timestamp', '?')
        cat = h.metadata.get('category', '?')
        msg_n = h.metadata.get('msg_count', '?')
        print(f"  [{ts}] {spk} ({msg_n}条) [{cat}]")
        print(f"    {h.text[:60].replace(chr(10), ' ')}...")
