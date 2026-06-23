"""
测试导入微信聊天记录到知识库
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, 'D:/qwen3-asr')

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'

from knowledge_store import init_knowledge_base, get_vectorstore, get_chunker, index_document

def test_import_wechat():
    """测试导入微信聊天记录"""
    # 初始化知识库
    print("🔄 正在初始化知识库...")
    init_knowledge_base(summarizer=None)
    
    # 导入测试文件
    test_file = "D:/qwen3-asr/knowledge_base/wechat/信竞家长交流群_测试.standard.md"
    
    print(f"🔄 正在导入: {test_file}")
    
    try:
        # 使用 index_document 导入（会自动分块、向量化、存储）
        result = index_document(test_file, category="微信聊天记录")
        print(f"✅ 导入成功！doc_id: {result.get('doc_id', 'unknown')}")
        print(f"   分块数: {result.get('chunk_count', 0)}")
        
        # 测试搜索
        print("\n🔍 测试搜索...")
        from knowledge_store import get_embedder
        embedder = get_embedder()
        
        # 生成查询向量
        query = "CSP初赛"
        query_embedding = embedder.embed_texts([query])[0]
        
        # 搜索
        vector_store = get_vectorstore()
        results = vector_store.search(query_embedding, top_k=3)
        
        print(f"找到 {len(results)} 条结果:")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r.metadata.get('speaker', '未知')} ({r.metadata.get('timestamp', '')})")
            print(f"   {r.text[:100]}...\n")
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_import_wechat()
