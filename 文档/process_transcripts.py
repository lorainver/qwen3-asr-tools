#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直播内容整理脚本
将口语化的直播记录整理成结构化的HTML文档
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

def clean_text(text):
    """清理口语化内容"""
    # 删除填充词
    fillers = [
        r'呃，?', r'嗯，?', r'啊，?', r'哎，?', r'那个，?',
        r'好不好\??', r'好吧[，。]?', r'好吧', r'对不对\??',
        r'是吧[，。]?', r'是不是[，。]?', r'对吧\??',
        r'我们来看一下，?', r'我们来看，?', r'然后的话，?',
        r'那所以，?', r'那这样一来的话，?', r'那我们，?',
        r'那这个，?', r'那现在，?', r'就是，?',
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
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # 清理多余空格
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'。\s*。', '。', text)

    return text.strip()

def extract_sections(text, title_keywords):
    """提取主题章节"""
    lines = text.split('\n')
    
    # 清理所有行
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 5:
            cleaned = clean_text(line)
            if cleaned:
                cleaned_lines.append(cleaned)
    
    # 如果内容较少，直接作为单章节
    if len(cleaned_lines) < 20:
        return [{
            'title': '内容概要',
            'num': '一',
            'content': cleaned_lines
        }]
    
    sections = []
    current_section = {'title': '内容概要', 'num': '一', 'content': []}
    section_idx = 0
    
    for line in cleaned_lines:
        matched = False
        
        # 检测题目标记
        if re.search(r'第[一二三四五六七八九十\d]+题', line):
            if current_section['content']:
                sections.append(current_section)
            section_idx = len(sections)
            num = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][min(section_idx, 9)]
            title_match = re.search(r'第[一二三四五六七八九十\d]+题[:：]?\s*(.+)', line)
            title = title_match.group(1)[:20] if title_match else line[:30]
            current_section = {
                'title': title if title else f'第{num}题',
                'num': num,
                'content': [line]
            }
            matched = True
        
        # 检测关键词
        if not matched:
            for i, kw in enumerate(title_keywords):
                if kw in line:
                    if current_section['content'] and len(current_section['content']) > 5:
                        sections.append(current_section)
                        section_idx = len(sections)
                        num = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][min(section_idx, 9)]
                        current_section = {
                            'title': kw,
                            'num': num,
                            'content': [line]
                        }
                        matched = True
                        break
        
        if not matched:
            current_section['content'].append(line)
    
    # 添加最后一个章节
    if current_section['content']:
        sections.append(current_section)
    
    # 如果章节过多，合并小章节
    if len(sections) > 8:
        merged = []
        current = {'title': '内容概要', 'num': '一', 'content': []}
        for sec in sections:
            current['content'].extend(sec['content'])
            if len(current['content']) >= 80:
                merged.append(current)
                num_idx = min(len(merged), 9)
                num = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][num_idx]
                current = {'title': f'第{num}部分', 'num': num, 'content': []}
        if current['content']:
            merged.append(current)
        sections = merged
    
    # 如果只有一两个章节，按段落自然分组
    if len(sections) <= 2 and len(cleaned_lines) > 50:
        chunk_size = len(cleaned_lines) // 4
        sections = []
        section_titles = ['内容概要', '核心要点', '详细分析', '总结建议']
        for i in range(4):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < 3 else len(cleaned_lines)
            num = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][i]
            sections.append({
                'title': section_titles[i],
                'num': num,
                'content': cleaned_lines[start:end]
            })
    
    return sections

def generate_html(title, sections):
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

        header .subtitle {{ font-size: 1rem; opacity: 0.9; }}

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
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
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

        section {{ margin-bottom: 32px; }}

        section h2 {{
            font-family: 'Noto Serif SC', serif;
            font-size: 1.4rem;
            color: var(--text-primary);
            padding-left: 16px;
            border-left: 4px solid var(--accent);
            margin-bottom: 16px;
        }}

        section h2 .section-num {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 400;
            display: block;
            margin-bottom: 4px;
        }}

        section h3 {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin: 20px 0 12px;
            font-weight: 600;
        }}

        section p {{
            color: var(--text-secondary);
            margin-bottom: 12px;
            text-align: justify;
        }}

        ul, ol {{
            margin: 12px 0 16px 24px;
            color: var(--text-secondary);
        }}

        li {{ margin-bottom: 8px; }}

        strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}

        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
            margin: 16px 0;
        }}

        .alert {{
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            border-left: 4px solid;
        }}

        .alert-gold {{ background: var(--highlight); border-color: var(--gold); }}
        .alert-success {{ background: #eaf5ed; border-color: var(--success); }}
        .alert-danger {{ background: #fdf0ec; border-color: var(--danger); }}
        .alert-info {{ background: #eaf2f8; border-color: var(--info); }}
        .alert-purple {{ background: var(--accent-bg); border-color: var(--accent); }}

        .tag {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin: 4px;
        }}

        .tag-purple {{ background: var(--accent-bg); color: var(--accent); }}
        .tag-gold {{ background: var(--highlight); color: var(--gold); }}
        .tag-green {{ background: #eaf5ed; color: var(--success); }}

        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}

        @media (max-width: 700px) {{
            .two-col {{ grid-template-columns: 1fr; }}
            header h1 {{ font-size: 1.5rem; }}
            main {{ padding: 20px; }}
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}

        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        thead {{ background: var(--accent); color: white; }}
        tbody tr:hover {{ background: var(--accent-bg); }}

        .content-block {{
            margin: 20px 0;
            padding: 16px;
            background: #fafafa;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <div class="subtitle">直播内容整理稿</div>
        </header>
        <nav>
            <h2>目录</h2>
            <ul id="toc">
'''

    # 生成目录
    for i, section in enumerate(sections):
        html += f'                <li><a href="#section{i+1}">{section["num"]}、{section["title"]}</a></li>\n'

    html += '''            </ul>
        </nav>
        <main>
'''

    # 生成章节内容
    for i, section in enumerate(sections):
        html += f'''            <section id="section{i+1}">
                <h2><span class="section-num">{section["num"]}</span>{section["title"]}</h2>
                <div class="content-block">
'''

        # 将内容分段
        content_text = ' '.join(section['content'])
        paragraphs = re.split(r'[。！？]', content_text)

        for para in paragraphs:
            para = para.strip()
            if para and len(para) > 10:
                html += f'                    <p>{para}。</p>\n'

        html += '''                </div>
            </section>
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

    # 根据文件名推断主题关键词
    if '试卷分析' in title or '测试' in title or '讲解' in title:
        keywords = ['试卷概览', '题目', '解题', '知识点', '学习建议', '考试要求', '难度分析']
    elif '少年班' in title or '升学' in title or '选拔' in title:
        keywords = ['政策', '报考', '选拔', '规划', '建议', '条件', '流程']
    elif '讲座' in title or '解读' in title:
        keywords = ['核心内容', '关键要点', '实施方案', '注意事项', '政策', '解读']
    else:
        keywords = ['主要内容', '关键信息', '详细分析', '总结', '建议']

    # 提取章节
    sections = extract_sections(content, keywords)

    # 如果没有提取到章节，创建默认章节
    if not sections:
        cleaned_content = clean_text(content)
        paragraphs = [p.strip() for p in cleaned_content.split('。') if p.strip() and len(p.strip()) > 10]

        sections = [{
            'title': '内容概要',
            'num': '一',
            'content': paragraphs[:50]
        }]

    # 生成HTML
    html = generate_html(title, sections)

    # 写入文件
    output_path = Path(output_dir) / f'{title}.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(output_path)

def main():
    input_dir = r'F:\屏幕录制\存档'
    output_dir = r'D:\qwen3-asr\文档\直播视频总结稿'

    # 获取所有待处理文件
    files = list(Path(input_dir).glob('*_qwen3.txt'))
    files.sort()

    print(f'找到 {len(files)} 个文件待处理')

    for i, file in enumerate(files):
        print(f'\n[{i+1}/{len(files)}] 处理: {file.name}')
        try:
            output = process_file(str(file), output_dir)
            print(f'  [OK] 已生成: {output}')
        except Exception as e:
            print(f'  [FAIL] 处理失败: {e}')

    print('\n处理完成！')

if __name__ == '__main__':
    main()
