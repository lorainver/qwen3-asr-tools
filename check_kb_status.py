"""查看知识库当前状态"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 查看所有文档
docs = vs.get_all_docs()
print('当前知识库中的文档：')
for d in docs:
    fn = d['filename']
    cnt = d['chunk_count']
    did = d['doc_id']
    print(f'  - {fn} ({cnt} chunks, doc_id={did})')
print(f'总计: {vs.count()} chunks')
