import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    c = f.read()
for m in re.finditer(r'id="([^"]+)"', c):
    if 'search' in m.group(1) or 'session' in m.group(1):
        line = c[:m.start()].count('\n') + 1
        print(f'L{line}: id="{m.group(1)}"')
