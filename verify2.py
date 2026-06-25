import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

checks = [
    ('toggleSearchScope function', 'function toggleSearchScope'),
    ('toggleSearchSessionType function', 'function toggleSearchSessionType'),
    ('renderWechatBubblesGrouped function', 'function renderWechatBubblesGrouped'),
    ('wechatState: searchScope', 'searchScope:'),
    ('wechatState: searchSessionType', 'searchSessionType:'),
    ('wechatState: searchTypeStats', 'searchTypeStats:'),
    ('search-type-filter div', 'id="search-type-filter"'),
    ('session-select-container div', 'id="session-select-container"'),
    ('searchScope === all', "searchScope === 'all'"),
    ('session_type= in URL', 'session_type='),
    ('typeStats.length check', 'typeStats.length'),
    ('GROUP BY type in UI', "typeName} <span"),
    ('.wechat-group-header style', 'wechat-group-header'),
]

for name, pattern in checks:
    ok = pattern in c
    print(f'  {"PASS" if ok else "FAIL"}: {name}')

# Check old session-select is NOT duplicated
old_select_count = c.count('id="wechat-session-select"')
print(f'\n  wechat-session-select count: {old_select_count} (should be 1)')

# Check old session-type-filter is removed
old_filter_count = c.count('id="wechat-session-type-filter"')
print(f'  wechat-session-type-filter (old) count: {old_filter_count} (should be 0)')

print(f'\n  File lines: {c.count(chr(10))}')
