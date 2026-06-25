with open('wechat_api.py', 'r', encoding='utf-8') as f:
    c = f.read()
import re
for m in re.finditer(r'session_type|search_by_keyword', c):
    line = c[:m.start()].count('\n') + 1
    print(f'L{line}: {c[m.start():m.start()+60]}')
