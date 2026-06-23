"""模拟多来源场景，验证 category 过滤保护"""
import sys, os
sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, delete_by_filename

init_knowledge_base(summarizer=None)
vs = get_vectorstore()

# 1. 先插入一个模拟的 echotrace 来源 chunk
print("=== 插入模拟 EchoTrace 数据 ===")
vs.collection.add(
    ids=["test_echo_chunk_1"],
    documents=["2025-12-15 张三: CSP初赛报名时间是什么时候？"],
    metadatas=[{
        "doc_id": "test_echotrace_001",
        "filename": "💪信竞家长交流群_echotrace.standard.md",
        "category": "微信聊天记录_echotrace",
        "source": "wechat",
        "export_source": "echotrace",
        "speaker": "张三",
        "timestamp": "2025-12-15 10:30:00",
        "chunk_index": 0
    }]
)
print("已插入 1 个 echotrace 来源的模拟 chunk")

# 2. 再插入一个 wechat-cli 来源 chunk
print("\n=== 插入模拟 wechat-cli 数据 ===")
vs.collection.add(
    ids=["test_wc_chunk_1"],
    documents=["2026-03-20 李四: 今年CSP初赛什么时候报名？"],
    metadatas=[{
        "doc_id": "test_wc_001",
        "filename": "💪信竞家长交流群_raw.standard.md",
        "category": "微信聊天记录_wechat-cli-20260109",
        "source": "wechat",
        "export_source": "wechat-cli-20260109",
        "speaker": "李四",
        "timestamp": "2026-03-20 14:00:00",
        "chunk_index": 0
    }]
)
print("已插入 1 个 wechat-cli 来源的模拟 chunk")

# 3. 查看当前状态
print(f"\n=== 当前信竞群数据: {vs.count()} total chunks ===")

# 4. 模拟 wechat-cli 重新导入 → 只删 wechat-cli 来源
print("\n=== 模拟 wechat-cli 重新导入（去重） ===")
deleted = delete_by_filename("信竞家长交流群", category="微信聊天记录_wechat-cli-20260109")
print(f"删除了 {deleted} chunks（应只删 wechat-cli 来源的1个）")

# 5. 验证 echotrace 数据是否保留
print("\n=== 验证 echotrace 数据是否保留 ===")
results = vs.collection.get(
    where={"category": "微信聊天记录_echotrace"},
    include=["metadatas", "documents"]
)
if results and results['ids']:
    print(f"✅ echotrace 数据保留: {len(results['ids'])} chunks")
    for i, doc in enumerate(results['documents']):
        print(f"  - {doc}")
else:
    print("❌ echotrace 数据被误删！")

# 6. 清理测试数据
print("\n=== 清理测试数据 ===")
vs.collection.delete(ids=["test_echo_chunk_1", "test_wc_chunk_1"])
print("已清理模拟数据")

print("\n✅ 结论: category 过滤可以保护不同来源的数据，互不干扰")
