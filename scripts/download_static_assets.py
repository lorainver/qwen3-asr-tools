import os
import re
import sys
import urllib.request
import urllib.error

# 定义路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
JS_DIR = os.path.join(STATIC_DIR, "js")
CSS_DIR = os.path.join(STATIC_DIR, "css")
FONTS_DIR = os.path.join(CSS_DIR, "fonts")

# 需要下载的核心前端库映射
CORE_ASSETS = {
    "js/marked.min.js": "https://cdn.jsdelivr.net/npm/marked@15.0.7/marked.min.js",
    "js/highlight.min.js": "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/highlight.min.js",
    "css/atom-one-dark.min.css": "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/atom-one-dark.min.css",
    "css/katex.min.css": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css",
    "js/katex.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js",
    "js/auto-render.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js",
    "js/mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js",
    "js/mermaid.esm.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11.4.0/dist/mermaid.esm.min.js"
}

def setup_directories():
    """创建所需的物理目录"""
    os.makedirs(JS_DIR, exist_ok=True)
    os.makedirs(CSS_DIR, exist_ok=True)
    os.makedirs(FONTS_DIR, exist_ok=True)
    print("[Dir] 基础目录初始化成功:")
    print(f"   -> JS 目录: {JS_DIR}")
    print(f"   -> CSS 目录: {CSS_DIR}")
    print(f"   -> Fonts 目录: {FONTS_DIR}")

def download_file(url, save_path):
    """通用下载文件函数（带进度提示与 User-Agent 伪装）"""
    print(f"[HTTP] 正在下载: {url} -> {os.path.relpath(save_path, BASE_DIR)}")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(save_path, 'wb') as f:
                f.write(response.read())
        return True
    except urllib.error.URLError as e:
        print(f"[Error] 下载失败: {url}。原因: {e}")
        return False
    except Exception as e:
        print(f"[Error] 发生意外错误: {e}")
        return False

def pull_katex_fonts(css_path):
    """解析 KaTeX CSS 并智能同步其中引用的 woff2/woff/ttf 字体"""
    print("[Parser] 正在分析 KaTeX CSS 关联字体...")
    if not os.path.exists(css_path):
        print("[Warning] 未找到 katex.min.css，跳过字体拉取。")
        return

    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配 CSS 中 url(...) 内引用的字体文件，如 url(fonts/KaTeX_Main-Regular.woff2)
    font_urls = re.findall(r'url\((fonts/[a-zA-Z0-9_\-\.]+)\)', content)
    unique_fonts = sorted(list(set(font_urls)))

    if not unique_fonts:
        print("[Warning] 无法在 KaTeX CSS 中解析出字体资产引用，可能已被内联或格式不匹配。")
        return

    print(f"[Fonts] 解析出 {len(unique_fonts)} 个独立字体依赖。正在开启自动抓取...")
    
    # 字体 CDN 根地址：基于 katex.min.css CDN 路径的 fonts/ 目录
    fonts_cdn_root = "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/"
    
    downloaded_count = 0
    for font_rel_path in unique_fonts:
        # 获取文件名 (例如 KaTeX_Main-Regular.woff2)
        font_name = os.path.basename(font_rel_path)
        font_url = f"{fonts_cdn_root}fonts/{font_name}"
        save_path = os.path.join(FONTS_DIR, font_name)
        
        # 如果文件已存在，跳过，节省下载时间
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            downloaded_count += 1
            continue
            
        success = download_file(font_url, save_path)
        if success:
            downloaded_count += 1

    print(f"[Fonts] 字体抓取收尾: 成功拉取/核对 {downloaded_count}/{len(unique_fonts)} 个 KaTeX 配套物理字体文件。")

def main():
    # 强制设置命令行输出为 utf-8（部分 windows 终端依然可用）
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
        
    print("=========================================")
    print("Web 工作站 - 前端静态资产本地化同步同步引擎")
    print("=========================================")
    
    # 1. 目录初始化
    setup_directories()
    
    # 2. 下载核心资产
    success_all = True
    katex_css_path = None
    
    for rel_path, url in CORE_ASSETS.items():
        save_path = os.path.join(STATIC_DIR, rel_path.replace("/", os.sep))
        
        # 记录 katex.min.css 的保存路径以供后续提取字体
        if rel_path == "css/katex.min.css":
            katex_css_path = save_path
            
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            print(f"[Skip] 资产已存在且有效，跳过下载: {rel_path}")
            continue
            
        success = download_file(url, save_path)
        if not success:
            success_all = False
            
    # 3. 解析并抓取 KaTeX 物理字体，为绝对离线做好最硬核的底座支撑
    if katex_css_path:
        pull_katex_fonts(katex_css_path)
        
    print("=========================================")
    if success_all:
        print("[Success] 所有前端核心库及配套字体均已成功下载至本地托管！")
        print("👉 现在您可以安全修改 templates/index.html 与 web_app.py 中的外部 CDN 挂载为 /static/ 路径。")
    else:
        print("[Warning] 静态资产下载中发生部分错误，请检查网络后重新运行本脚本。")
    print("=========================================")

if __name__ == "__main__":
    main()
