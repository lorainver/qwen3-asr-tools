#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直播内容整理脚本 v2
将口语化的直播记录整理成结构化的HTML文档
重点：内容总结、提炼要点、去除冗余
"""

import os
import re
import sys
from pathlib import Path

# 设计规范色彩系统
COLORS = {
    'bg': '#faf9f6',
    'surface': '#ffffff',
    'accent': '#6b2d5b',
    'accent_light': '#8e4585',
    'accent_bg': '#f5eef3',
    'gold': '#b8860b',
    'text_primary': '#1a1a1a',
    'text_secondary': '#4a4a4a',
    'text_muted': '#7a7570',
    'border': '#e2ddd6',
    'highlight': '#fff3cd',
    'success': '#2d6b3f',
    'danger': '#8b2500',
    'info': '#1a5276',
}

def clean_and_summarize(text):
    """清理并总结文本内容"""
    # 删除填充词和口语化表达
    fillers = [
        r'呃，?', r'嗯，?', r'啊，?', r'哎，?', r'那个，?',
        r'好不好\??', r'好吧[，。]?', r'好吧', r'对不对\??',
        r'是吧[，。]?', r'是不是[，。]?', r'对吧\??',
        r'我们来看一下，?', r'我们来看，?', r'然后的话，?',
        r'那所以，?', r'那这样一来的话，?', r'那我们，?',
        r'那这个，?', r'那现在，?', r'就是，?',
        r'可以打一个[^。]+。', r'没有关注的朋友[^。]+。',
        r'大家记得[^。]+。', r'大家可以[^。]+。',
    ]

    for filler in fillers:
        text = re.sub(filler, '', text)

    # 口语转书面语
    replacements = {
        '就是说': '即',
        '其实就是': '即',
        '我告诉你': '需要注意的是',
        '大家知道': '',
        '我们来看看': '分析',
        '我们来看': '分析',
        '那我们': '',
        '那所以': '因此',
        '那这个': '该',
        '那现在': '当前',
        '然后的话': '接着',
        '这个时候': '此时',
        '那这样一来的话': '因此',
        '比如说': '例如',
        '比如说吧': '例如',
        '对吧': '',
        '是吧': '',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # 清理多余空格和重复标点
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'。\s*。+', '。', text)
    text = re.sub(r'，\s*，+', '，', text)
    
    return text.strip()

def extract_key_points(text, max_points=8):
    """提取关键要点"""
    points = []
    sentences = re.split(r'[。！？]', text)
    
    for sent in sentences:
        sent = sent.strip()
        # 跳过太短或太长的句子
        if len(sent) < 15 or len(sent) > 150:
            continue
        
        # 识别关键句子（包含重要信息的）
        important_patterns = [
            r'建议', r'需要', r'要求', r'应该', r'必须',
            r'重要', r'注意', r'关键', r'核心', r'首先',
            r'\d+月', r'\d+年', r'\d+分', r'\d+人',
            r'政策', r'变化', r'调整', r'新增', r'取消',
            r'第一', r'第二', r'第三', r'最后',
            r'录取', r'报名', r'考试', r'选拔',
        ]
        
        is_important = any(re.search(p, sent) for p in important_patterns)
        
        # 检查是否是陈述性句子（而非提问）
        is_statement = not any(q in sent for q in ['？', '?', '什么', '怎么', '如何', '为什么'])
        
        if is_important and is_statement:
            # 清理句子
            cleaned = clean_and_summarize(sent)
            if cleaned and len(cleaned) > 15:
                points.append(cleaned)
    
    # 去重并限制数量
    unique_points = list(dict.fromkeys(points))
    return unique_points[:max_points]

def detect_sections(text):
    """智能检测章节"""
    sections = []
    
    # 检测题目标记
    question_pattern = r'第[一二三四五六七八九十\d]+题'
    questions = list(re.finditer(question_pattern, text))
    
    if len(questions) >= 3:
        # 按题目分章节
        for i, match in enumerate(questions):
            start = match.start()
            end = questions[i+1].start() if i+1 < len(questions) else len(text)
            section_text = text[start:end]
            
            title = match.group()
            # 尝试提取题目主题
            after_title = section_text[len(title):50]
            if after_title:
                topic = re.search(r'[：:]\s*(.{5,20})', after_title)
                if topic:
                    title = title + ' - ' + topic.group(1).strip()
            
            sections.append({
                'title': title,
                'content': section_text
            })
    
    return sections

def create_content_summary(text, title):
    """创建内容总结"""
    # 清理文本
    cleaned = clean_and_summarize(text)
    
    # 提取关键要点
    key_points = extract_key_points(cleaned, max_points=10)
    
    # 尝试检测章节
    sections = detect_sections(cleaned)
    
    # 如果没有明显的题目章节，按主题分块
    if not sections:
        # 将文本分成4-5个逻辑段落
        sentences = [s.strip() for s in re.split(r'[。！？]', cleaned) if s.strip() and len(s.strip()) > 20]
        
        if len(sentences) > 30:
            # 智能分组
            chunk_size = len(sentences) // 5
            section_titles = ['概述', '核心要点', '详细内容', '重要建议', '总结']
            
            for i in range(5):
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < 4 else len(sentences)
                if start < len(sentences):
                    sections.append({
                        'title': section_titles[i],
                        'content': '。'.join(sentences[start:end])
                    })
        else:
            sections.append({
                'title': '内容概要',
                'content': '。'.join(sentences[:20])
            })
    
    return sections, key_points

def generate_html(title, sections, key_points):
    """生成HTML文档"""
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: {COLORS['bg']};
            --surface: {COLORS['surface']};
            --accent: {COLORS['accent']};
            --accent-light: {COLORS['accent_light']};
            --accent-bg: {COLORS['accent_bg']};
            --gold: {COLORS['gold']};
            --text-primary: {COLORS['text_primary']};
            --text-secondary: {COLORS['text_secondary']};
            --text-muted: {COLORS['text_muted']};
            --border: {COLORS['border']};
            --highlight: {COLORS['highlight']};
            --success: {COLORS['success']};
            --danger: {COLORS['danger']};
            --info: {COLORS['info']};
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Noto Sans SC', sans-serif;
            background: var(--bg);
            color: var(--text-primary);
            line-height: 1.8;
            padding: 20px;
        }}

        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            color: white;
            padding: 40px 32px;
        }}

        header h1 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 12px;
        }}

        header .subtitle {{
            font-size: 1rem;
            opacity: 0.9;
        }}

        .summary-box {{
            background: var(--accent-bg);
            padding: 24px 32px;
            border-bottom: 1px solid var(--border);
        }}

        .summary-box h2 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 1.2rem;
            color: var(--accent);
            margin-bottom: 16px;
        }}

        .summary-box ul {{
            list-style: none;
        }}

        .summary-box li {{
            position: relative;
            padding-left: 24px;
            margin-bottom: 12px;
            color: var(--text-secondary);
        }}

        .summary-box li::before {{
            content: "▸";
            position: absolute;
            left: 0;
            color: var(--gold);
            font-weight: bold;
        }}

        nav {{
            background: var(--surface);
            padding: 20px 32px;
            border-bottom: 1px solid var(--border);
        }}

        nav h2 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 1.1rem;
            color: var(--accent);
            margin-bottom: 12px;
        }}

        nav ul {{
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 8px;
        }}

        nav li a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.95rem;
            padding: 6px 0;
            display: inline-block;
            transition: color 0.2s;
        }}

        nav li a:hover {{ color: var(--accent); }}

        main {{ padding: 32px; }}

        section {{
            margin-bottom: 40px;
        }}

        section h2 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 1.4rem;
            color: var(--text-primary);
            padding-left: 16px;
            border-left: 4px solid var(--accent);
            margin-bottom: 20px;
        }}

        section h3 {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin: 24px 0 12px;
            font-weight: 600;
        }}

        section p {{
            color: var(--text-secondary);
            margin-bottom: 14px;
            text-align: justify;
            line-height: 2;
        }}

        section ul, section ol {{
            margin: 14px 0 14px 28px;
            color: var(--text-secondary);
        }}

        li {{ margin-bottom: 10px; line-height: 1.8; }}

        strong {{
            color: var(--accent);
            font-weight: 600;
        }}

        .alert {{
            padding: 18px 22px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid;
            background: #fafafa;
        }}

        .alert-gold {{ background: var(--highlight); border-color: var(--gold); }}
        .alert-success {{ background: #eaf5ed; border-color: var(--success); }}
        .alert-danger {{ background: #fdf0ec; border-color: var(--danger); }}
        .alert-info {{ background: #eaf2f8; border-color: var(--info); }}
        .alert-purple {{ background: var(--accent-bg); border-color: var(--accent); }}

        .alert-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }}

        .tag {{
            display: inline-block;
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin: 4px;
            font-weight: 500;
        }}

        .tag-purple {{ background: var(--accent-bg); color: var(--accent); }}
        .tag-gold {{ background: var(--highlight); color: var(--gold); }}
        .tag-green {{ background: #eaf5ed; color: var(--success); }}
        .tag-blue {{ background: #eaf2f8; color: var(--info); }}

        .highlight-text {{
            background: linear-gradient(transparent 60%, var(--highlight) 60%);
            padding: 0 4px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            padding: 14px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        thead {{
            background: var(--accent);
            color: white;
        }}

        thead th {{
            font-weight: 600;
        }}

        tbody tr:hover {{
            background: var(--accent-bg);
        }}

        .content-card {{
            background: #fafafa;
            border-radius: 8px;
            padding: 20px;
            margin: 16px 0;
        }}

        @media (max-width: 700px) {{
            header h1 {{ font-size: 1.5rem; }}
            main {{ padding: 20px; }}
            .summary-box, nav {{ padding: 16px 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <div class="subtitle">直播内容整理稿</div>
        </header>
'''

    # 添加要点总结框
    if key_points:
        html += '''        <div class="summary-box">
            <h2>核心要点</h2>
            <ul>
'''
        for point in key_points[:8]:
            html += f'                <li>{point}</li>\n'
        html += '''            </ul>
        </div>
'''

    # 添加目录
    html += '''        <nav>
            <h2>目录</h2>
            <ul>
'''
    section_nums = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    for i, section in enumerate(sections[:10]):
        num = section_nums[i] if i < len(section_nums) else str(i+1)
        html += f'                <li><a href="#section{i+1}">{num}、{section["title"]}</a></li>\n'

    html += '''            </ul>
        </nav>
        <main>
'''

    # 生成章节内容
    for i, section in enumerate(sections[:10]):
        num = section_nums[i] if i < len(section_nums) else str(i+1)
        html += f'''            <section id="section{i+1}">
                <h2>{section["title"]}</h2>
'''

        # 处理章节内容
        content = section['content']
        sentences = [s.strip() for s in re.split(r'[。！？]', content) if s.strip() and len(s.strip()) > 15]
        
        # 将句子组织成段落
        paragraphs = []
        current_para = []
        for sent in sentences:
            current_para.append(sent)
            if len(current_para) >= 3:  # 每3句一个段落
                paragraphs.append('。'.join(current_para) + '。')
                current_para = []
        
        if current_para:
            paragraphs.append('。'.join(current_para) + ('。' if not current_para[0].endswith('。') else ''))
        
        # 输出段落
        for para in paragraphs[:6]:  # 每节最多6段
            html += f'                <p>{para}</p>\n'

        html += '''            </section>
'''

    html += '''        </main>
    </div>
</body>
</html>
'''

    return html

def process_file(input_path, output_dir):
    """处理单个文件"""
    # 读取文件
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取标题
    title = Path(input_path).stem.replace('_qwen3', '')

    # 创建内容总结
    sections, key_points = create_content_summary(content, title)

    # 生成HTML
    html = generate_html(title, sections, key_points)

    # 写入文件
    output_path = Path(output_dir) / f'{title}.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(output_path), len(key_points)

def main():
    input_dir = r'F:\屏幕录制\存档'
    output_dir = r'D:\qwen3-asr\文档\直播视频总结稿'

    # 获取所有待处理文件
    files = list(Path(input_dir).glob('*_qwen3.txt'))
    files.sort()

    print(f'找到 {len(files)} 个文件待处理\n')

    success = 0
    failed = 0

    for i, file in enumerate(files):
        print(f'[{i+1}/{len(files)}] {file.stem[:40]}...')
        try:
            output, points = process_file(str(file), output_dir)
            print(f'  ✓ 已生成 ({points}个要点)')
            success += 1
        except Exception as e:
            print(f'  ✗ 失败: {e}')
            failed += 1

    print(f'\n处理完成！成功: {success}, 失败: {failed}')

if __name__ == '__main__':
    main()
