import sys
from web_searcher import get_searcher

def test_search():
    searcher = get_searcher()
    # 优先从命令行获取查询词
    query = sys.argv[1] if len(sys.argv) > 1 else "重庆今天天气"
    
    print(f"正在搜索: {query}...")
    results = searcher.search(query, max_results=5)
    
    if not results:
        print("未搜到结果！")
        return

    print(f"\n找到 {len(results)} 条结果：")
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r.title}")
        print(f"    摘要: {r.snippet}")
        print("-" * 20)

    context = searcher.format_for_llm(results)
    print("\n--- 注入模型的上下文预览 ---")
    print(context)

if __name__ == "__main__":
    test_search()
