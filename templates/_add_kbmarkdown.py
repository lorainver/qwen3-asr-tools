# -*- coding: utf-8 -*-
"""Add kbRenderMarkdown function to wechat_console.html"""
import sys

with open(r'D:\qwen3-asr\templates\wechat_console.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the closing script tag position
insert_pos = content.rfind('</script>\n</body>')

if insert_pos == -1:
    # Try alternative
    insert_pos = content.rfind('</script>')
    # Find the last </script> 
    last_script = content.rindex('</script>')
    insert_pos = last_script

# The function to add - use raw strings to avoid escaping issues
func = """

        // Markdown render function for AI analysis
        function kbRenderMarkdown(text) {
            if (!text) return '';
            try {
                var mermaidBlocks = [];
                text = text.replace(/```mermaid\n([\s\S]*?)```/g, function(match, code) {
                    var idx = mermaidBlocks.length;
                    mermaidBlocks.push(code.trim());
                    return '%%MERMAID_' + idx + '%%';
                });

                var mathBlocks = [];
                text = text.replace(/\$\$([\s\S]*?)\$\$/g, function(match, formula) {
                    var idx = mathBlocks.length;
                    mathBlocks.push({ formula: formula.trim(), display: true });
                    return '%%MATH_BLOCK_' + idx + '%%';
                });
                text = text.replace(/\$([^$\n]+?)\$/g, function(match, formula) {
                    var idx = mathBlocks.length;
                    mathBlocks.push({ formula: formula.trim(), display: false });
                    return '%%MATH_INLINE_' + idx + '%%';
                });

                var html = marked.parse(text);

                for (var i = 0; i < mathBlocks.length; i++) {
                    var item = mathBlocks[i];
                    var key = item.display ? '%%MATH_BLOCK_' + i + '%%' : '%%MATH_INLINE_' + i + '%%';
                    try {
                        var rendered = katex.renderToString(item.formula, {
                            displayMode: item.display, throwOnError: false, trust: true
                        });
                        html = html.replace(key, rendered);
                    } catch (e) {
                        html = html.replace(key, item.display ? '$$' + item.formula + '$$' : '$' + item.formula + '$');
                    }
                }

                for (var i = 0; i < mermaidBlocks.length; i++) {
                    var code = mermaidBlocks[i];
                    var plh = '%%MERMAID_' + i + '%%';
                    var cid = 'mermaid-' + Date.now() + '-' + i;
                    var container = '<div class="mermaid-container" id="' + cid + '" data-mermaid-code="' + encodeURIComponent(code) + '">' +
                        '<div class="mermaid-loading">\U0001f504 图表加载中...</div></div>';
                    html = html.replace(plh, container);
                }

                return html;
            } catch (e) {
                return escapeHtml(text);
            }
        }
"""

new_content = content[:insert_pos] + func + content[insert_pos:]

with open(r'D:\qwen3-asr\templates\wechat_console.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Done. {len(new_content)} bytes total.')
