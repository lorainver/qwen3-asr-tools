with open('templates/index.html', 'r', encoding='utf-8') as f:
    c = f.read()
import re
for m in re.finditer(r"getElementById\('wechat-session-select'\)", c):
    line = c[:m.start()].count('\n') + 1
    print(f'L{line}: {c[m.start():m.start()+80]}')
