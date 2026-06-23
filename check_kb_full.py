"""全面检查知识库状态"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()
docs = vs.get_all_docs()

print(f"总 chunks: {vs.count()}, 总 docs: {len(docs)}")
for d in docs:
    fn = d.get('filename', '?')
    cnt = d.get('chunk_count', '?')
    cat = d.get('category', '?')
    print(f"  {fn}: {cnt} chunks (category={cat})")
