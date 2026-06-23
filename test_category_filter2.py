"""模拟多来源场景，验证 category 过滤保护（不插入数据，纯逻辑测试）"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, delete_by_filename

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 当前知识库状态
docs = vs.get_all_docs()
print("=== 当前知识库文档 ===")
for d in docs:
    fn = d['filename']
    cnt = d['chunk_count']
    cat = d.get('category', '?')
    print(f"  {fn}: {cnt} chunks (category={cat})")

# 测试1: 用 echotrace category 删除信竞群 → 不应删除 wechat-cli 数据
print("\n=== 测试1: delete_by_filename('信竞家长交流群', category='微信聊天记录_echotrace') ===")
deleted1 = delete_by_filename("信竞家长交流群", category="微信聊天记录_echotrace")
print(f"删除了 {deleted1} chunks（应为0，因为当前没有 echotrace 数据）")

# 测试2: 用 wechat-cli category 删除金佛山群 → 应该删除
print("\n=== 测试2: delete_by_filename('金佛山', category='微信聊天记录_wechat-cli-20260109') ===")
deleted2 = delete_by_filename("金佛山", category="微信聊天记录_wechat-cli-20260109")
print(f"删除了 {deleted2} chunks（应>0）")

# 测试3: 不指定 category 删除金佛山群 → 删除所有来源
print("\n=== 测试3: delete_by_filename('金佛山') — 不限 category ===")
deleted3 = delete_by_filename("金佛山")
print(f"删除了 {deleted3} chunks（应=0，因为测试2已删完）")

# 最终状态
docs2 = vs.get_all_docs()
print(f"\n=== 最终: {vs.count()} total chunks, {len(docs2)} docs ===")
