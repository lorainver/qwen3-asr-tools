import json, urllib.request, urllib.parse

base = 'http://127.0.0.1:8000'

def test(params):
    url = base + '/api/wechat/search/keyword?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        d = json.loads(r.read())
    data = d['data']
    print(f"keyword={params.get('keyword')!r}, session_type={params.get('session_type')!r}")
    print(f"  total={data['total']}, type_stats={data['type_stats']}")
    if data['results']:
        print(f"  first result: type={data['results'][0].get('session_type')!r}, name={data['results'][0].get('session_name')!r}")
    print()

tests = [
    {'keyword': '数学', 'limit': 3},
    {'keyword': '数学', 'limit': 3, 'session_type': '群聊'},
    {'keyword': '数学', 'limit': 3, 'session_type': '私聊'},
    {'keyword': '数学', 'limit': 3, 'session_type': '公众号'},
]
for t in tests:
    test(t)
