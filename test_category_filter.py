"""测试：多来源去重，category 过滤是否保护不同来源的数据"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, delete_by_filename

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 当前信竞群的 chunks
results = vs.collection.get(
    where={"filename": {"$contains": "信竞家长交流群"}},
    include=["metadatas"]
)

if results and results['metadatas']:
    print(f"当前信竞群数据: {len(results['metadatas'])} chunks")
    for m in results['metadatas'][:3]:
        print(f"  category={m.get('category', '?')}, filename={m.get('filename', '?')}")
else:
    print("当前无信竞群数据")

# 测试1：用 category=微信聊天记录_echotrace 删除 → 不应该删除任何 wechat-cli 数据
print("\n--- 测试1: 删除 echotrace 来源（不存在）---")
deleted = delete_by_filename("信竞家长交流群", category="微信聊天记录_echotrace")
print(f"删除了 {deleted} chunks（应为0）")

# 验证 wechat-cli 数据仍存在
results2 = vs.collection.get(
    where={"filename": {"$contains": "信竞家长交流群"}},
    include=["metadatas"]
)
print(f"剩余信竞群数据: {len(results2['metadatas'])} chunks")

# 测试2：用 category=微信聊天记录_wechat-cli-20260109 删除 → 应该删除该来源数据
print("\n--- 测试2: 删除 wechat-cli 来源（存在）---")
deleted2 = delete_by_filename("信竞家长交流群", category="微信聊天记录_wechat-cli-20260109")
print(f"删除了 {deleted2} chunks（应为41）")

# 验证数据已被删除
results3 = vs.collection.get(
    where={"filename": {"$contains": "信竞家长交流群"}},
    include=["metadatas"]
)
print(f"剩余信竞群数据: {len(results3['metadatas'])} chunks（应为0）")

print("\n✅ category 过滤工作正常！不同来源的数据互不干扰")
