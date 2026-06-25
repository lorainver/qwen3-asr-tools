import json, urllib.request
url = 'http://127.0.0.1:8000/api/wechat/search/keyword?keyword=%E6%95%B0%E5%AD%A6&limit=3&session_type=%E7%BE%A4%E8%81%8A'
with urllib.request.urlopen(url) as r:
    d = json.loads(r.read())
print('success:', d.get('success'))
print('total:', d.get('data', {}).get('total'))
print('type_stats:', d.get('data', {}).get('type_stats'))
print('session_stats count:', len(d.get('data', {}).get('session_stats', [])))
print('first result type:', d.get('data', {}).get('results', [{}])[0].get('session_type'))
