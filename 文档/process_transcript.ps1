# HTML文档生成器 - 直播内容整理脚本
# 根据用户提供的模板规则处理口语化文本

param(
    [string]$InputFile,
    [string]$OutputFile
)

# 读取输入文件
$content = Get-Content $InputFile -Raw -Encoding UTF8

# 提取文件名作为标题基础
$fileName = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)
$title = $fileName -replace '_qwen3$', ''

# 去除口语化标记和冗余内容
$processed = $content

# 删除常见口语填充词
$fillers = @(
    '呃，?', '嗯，?', '啊，?', '哎，?', '那个，?', '就是说，?',
    '大家知道，?', '对不对', '我告诉你', '好不好\?',
    '好吧[，。]?', '好吧', '是不是[，。]?', '是吧[，。]?',
    '可以打一个[^。]+。', '没有关注的朋友[^。]+。',
    '我们来看一下，?', '我们再来看一下，?',
    '我们来看，?', '然后的话，?', '这个时候，?',
    '那所以，?', '那这样一来的话，?',
    '那我们，?', '那这个，?', '那现在，?',
    '就是，?', '其实是，?', '应该是，?',
    '可能会，?', '应该会，?', '应该是会，?',
    '\[.*?\]', '（[^）]*）'
)

foreach ($filler in $fillers) {
    $processed = $processed -replace $filler, ''
}

# 口语转书面语
$replacements = @{
    '就是说' = '即'
    '其实就是' = '即'
    '我告诉你' = '需要注意的是'
    '大家知道' = ''
    '我们来看看' = '分析'
    '我们来看' = '分析'
    '那我们' = ''
    '那所以' = '因此'
    '那这个' = '该'
    '那现在' = '当前'
    '然后的话' = '接着'
    '这个时候' = '此时'
    '那这样一来的话' = '因此'
    '对吧\?' = ''
    '是吧\?' = ''
    '好不好' = ''
    '好吧' = ''
}

foreach ($key in $replacements.Keys) {
    $processed = $processed -replace $key, $replacements[$key]
}

# 清理多余空格和空行
$processed = $processed -replace '\s+', ' '
$processed = $processed -replace '。\s*。', '。'
$processed = $processed.Trim()

# 按句号分割成段落
$sentences = $processed -split '。' | Where-Object { $_.Trim().Length -gt 10 }

# 生成HTML
$html = @"
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$title</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #faf9f6;
            --surface: #ffffff;
            --accent: #6b2d5b;
            --accent-light: #8e4585;
            --accent-bg: #f5eef3;
            --gold: #b8860b;
            --text-primary: #1a1a1a;
            --text-secondary: #4a4a4a;
            --text-muted: #7a7570;
            --border: #e2ddd6;
            --highlight: #fff3cd;
            --success: #2d6b3f;
            --danger: #8b2500;
            --info: #1a5276;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Noto Sans SC', sans-serif;
            background: var(--bg);
            color: var(--text-primary);
            line-height: 1.8;
            padding: 20px;
        }

        .container {
            max-width: 960px;
            margin: 0 auto;
            background: var(--surface);
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }

        header {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            color: white;
            padding: 40px 32px;
        }

        header h1 {
            font-family: 'Noto Serif SC', serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 12px;
        }

        header .subtitle {
            font-size: 1rem;
            opacity: 0.9;
        }

        nav {
            background: var(--surface);
            padding: 20px 32px;
            border-bottom: 1px solid var(--border);
        }

        nav h2 {
            font-family: 'Noto Serif SC', serif;
            font-size: 1.1rem;
            color: var(--accent);
            margin-bottom: 12px;
        }

        nav ul {
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 8px;
        }

        nav li a {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.95rem;
            padding: 6px 0;
            display: inline-block;
            transition: color 0.2s;
        }

        nav li a:hover {
            color: var(--accent);
        }

        main {
            padding: 32px;
        }

        section {
            margin-bottom: 32px;
        }

        section h2 {
            font-family: 'Noto Serif SC', serif;
            font-size: 1.4rem;
            color: var(--text-primary);
            padding-left: 16px;
            border-left: 4px solid var(--accent);
            margin-bottom: 16px;
        }

        section h2 .section-num {
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 400;
            display: block;
            margin-bottom: 4px;
        }

        section h3 {
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin: 20px 0 12px;
            font-weight: 600;
        }

        section p {
            color: var(--text-secondary);
            margin-bottom: 12px;
            text-align: justify;
        }

        ul, ol {
            margin: 12px 0 16px 24px;
            color: var(--text-secondary);
        }

        li {
            margin-bottom: 8px;
        }

        strong {
            color: var(--text-primary);
            font-weight: 600;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
            margin: 16px 0;
        }

        .alert {
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            border-left: 4px solid;
        }

        .alert-gold {
            background: var(--highlight);
            border-color: var(--gold);
        }

        .alert-success {
            background: #eaf5ed;
            border-color: var(--success);
        }

        .alert-danger {
            background: #fdf0ec;
            border-color: var(--danger);
        }

        .alert-info {
            background: #eaf2f8;
            border-color: var(--info);
        }

        .alert-purple {
            background: var(--accent-bg);
            border-color: var(--accent);
        }

        .tag {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin: 4px;
        }

        .tag-purple { background: var(--accent-bg); color: var(--accent); }
        .tag-gold { background: var(--highlight); color: var(--gold); }
        .tag-green { background: #eaf5ed; color: var(--success); }
        .tag-red { background: #fdf0ec; color: var(--danger); }
        .tag-blue { background: #eaf2f8; color: var(--info); }

        .two-col {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }

        @media (max-width: 700px) {
            .two-col {
                grid-template-columns: 1fr;
            }
            header h1 {
                font-size: 1.5rem;
            }
            main {
                padding: 20px;
            }
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        thead {
            background: var(--accent);
            color: white;
        }

        tbody tr:hover {
            background: var(--accent-bg);
        }

        .content-block {
            margin: 20px 0;
            padding: 16px;
            background: #fafafa;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>$title</h1>
            <div class="subtitle">直播内容整理稿</div>
        </header>
        <nav>
            <h2>目录</h2>
            <ul id="toc">
                <li><a href="#section1">一、内容概要</a></li>
            </ul>
        </nav>
        <main>
            <section id="section1">
                <h2><span class="section-num">一</span>内容概要</h2>
                <div class="content-block">
$($sentences | Select-Object -First 20 | ForEach-Object { "<p>$_。</p>" })
                </div>
            </section>
        </main>
    </div>
</body>
</html>
"@

# 写入输出文件
$html | Out-File -FilePath $OutputFile -Encoding UTF8NoBOM

Write-Host "已生成: $OutputFile"
