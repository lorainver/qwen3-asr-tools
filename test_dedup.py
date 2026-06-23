"""测试去重功能"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, delete_by_filename

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 测试删除"信竞家长交流群"
print('删除前：')
docs = vs.get_all_docs()
for d in docs:
    if '信竞' in d['filename']:
        print(f'  - {d["filename"]} ({d["chunk_count"]} chunks)')

print('\n执行删除...')
deleted = delete_by_filename('信竞家长交流群')
print(f'删除了 {deleted} 个 chunks')

print('\n删除后：')
docs = vs.get_all_docs()
for d in docs:
    if '信竞' in d['filename']:
        print(f'  - {d["filename"]} ({d["chunk_count"]} chunks)')
