import re
import sys
import os

# 将项目根目录加入路径，以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from summarizer import LongTextSummarizer
    from config_loader import config
    print("Success: Imported project modules")
except ImportError as e:
    print(f"Error: Import failed: {e}")
    sys.exit(1)

def clean_keywords(keywords):
    """模拟 ai_worker.py 中的清洗逻辑"""
    # 1. 换行符替换为空格
    keywords = keywords.replace("\n", " ").replace("\r", " ")
    
    # 2. 正则去掉开头的数字序号 (如 "1. ", "2, ")
    keywords = re.sub(r'^\d+[\.、\s:-]+', '', keywords)
    
    # 3. 去除常见的前缀
    for prefix in ["关键词：", "关键词:", "Keywords:", "搜索词：", "搜索关键词："]:
        if keywords.startswith(prefix):
            keywords = keywords[len(prefix):].strip()
            
    # 4. 去除引号和多余空格
    keywords = keywords.replace('"', '').replace("'", "").strip()
    return keywords

def test_optimization():
    report_path = "d:/qwen3-asr/scratch/query_test_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 关键词提取优化测试报告\n\n")
        
        print("--- Loading Model (Qwen-3B) ---")
        summarizer = LongTextSummarizer()
        summarizer.switch_model("qwen-3b")
        
        test_cases = [
            "请用温柔的语气给小朋友讲讲：寒战 1994 是系列电影吗？还有哪些？",
            "我想了解下量子纠缠的最新进展，最好是 2024 年以后的重大实验结果。",
            "帮我查查今天重庆的天气，要详细一点的，包括穿衣建议。",
            "那个穿着红色钢铁战衣、胸口有个发光圆圈的超级英雄是谁演的？我想看他的详细资料。",
            "对比一下 iPhone 17 Pro 和 三星 S26 Ultra 的摄像头参数，哪个更强？",
            "嘿 AI，你能帮我个忙吗？我最近在写报告，需要知道微软现在的 CEO 是谁，还有他们最近一季度的财报表现。",
            "2026 年 5 月 15 日 NVIDIA 的股价是多少？或者最近的趋势也行。",
            "英国现在的首相是谁？另外他们下次大选是什么时候？"
        ]
        
        for i, user_query in enumerate(test_cases, 1):
            # 构造 Prompt
            keyword_prompt = f"请将以下问题提炼为 3 个搜索关键词，用空格隔开。严禁使用序号，严禁换行，直接输出关键词。\n\n问题：{user_query}"
            
            # 调用模型获取原始输出
            raw_output = summarizer.chat([{"role": "user", "content": keyword_prompt}])
            # 应用清洗逻辑
            final_keywords = clean_keywords(raw_output)
            
            f.write(f"### 测试用例 {i}\n")
            f.write(f"- **原始问题**: {user_query}\n")
            f.write(f"- **模型原始输出**: `{raw_output}`\n")
            f.write(f"- **最终清洗结果**: `{final_keywords}`\n\n")
            print(f"Test Case {i} completed.")
    
    print(f"\nReport generated at: {report_path}")

if __name__ == "__main__":
    test_optimization()
