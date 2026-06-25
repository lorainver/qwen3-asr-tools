with open('templates/index.html', 'r', encoding='utf-8') as f:
    c = f.read()
import re
id_counts = {}
for m in re.finditer(r'id="([^"]+)"', c):
    id_counts[m.group(1)] = id_counts.get(m.group(1), 0) + 1
duplicates = {k: v for k, v in id_counts.items() if v > 1 and 'wechat' in k}
print('Duplicate wechat IDs:', duplicates if duplicates else 'None')
checks = [
    'wechat-search-session-select',
    'search-type-filter',
    'session-select-container',
    'function toggleSearchScope',
    'function renderWechatBubblesGrouped',
    'function toggleSearchSessionType',
]
for ch in checks:
    print(f'  {"OK" if ch in c else "MISSING"}: {ch}')
print(f'wechat-session-select: {c.count("id=\"wechat-session-select\"")} occurrences')
print(f'wechat-search-session-select: {c.count("id=\"wechat-search-session-select\"")} occurrences')
print(f'Total lines: {c.count(chr(10))}')
