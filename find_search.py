import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

for func in ['let wechatState', 'var wechatState', 'const wechatState']:
    m = re.search(re.escape(func), c)
    if m:
        line = c[:m.start()].count('\n') + 1
        print(f'{func} at L{line}')

for pat in ['wechat-keyword-input', 'wechat-session-select', 'wechat-sender-input', 'wechat-search-section', '微信搜索']:
    m = re.search(r'id=["\']' + re.escape(pat), c)
    if m:
        line = c[:m.start()].count('\n') + 1
        print(f'id={pat} at L{line}')

# Find the wechatState definition block
m = re.search(r'let wechatState\s*=', c)
if m:
    line = c[:m.start()].count('\n') + 1
    print(f'wechatState block at L{line}')
    # Print next 10 lines
    end = c.find('\n', m.end())
    for i in range(10):
        end = c.find('\n', end + 1)
        if end == -1: break
    print(c[m.start():end][:300])
