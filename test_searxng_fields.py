import requests
import json

session = requests.Session()
session.trust_env = False
r = session.get(
    'http://192.168.31.132:8081/search',
    params={'q': 'Python latest version', 'format': 'json', 'language': 'zh-CN'},
    timeout=15,
    proxies={'http': None, 'https': None}
)
data = r.json()

# 打印第一条结果的全部字段
if data.get('results'):
    print('=== First result fields ===')
    first = data['results'][0]
    for k, v in first.items():
        val = str(v)[:300] if len(str(v)) > 300 else str(v)
        print(f'  {k}: {val}')
    print(f'\n=== Total {len(data["results"])} results ===')

print('\n=== Top-level fields ===')
for k in data.keys():
    if k != 'results':
        print(f'  {k}: {str(data[k])[:100]}')