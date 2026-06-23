"""获取群聊列表（正确处理 UTF-8 输出）"""
import subprocess, json, os, sys

# Use the venv's Python which should handle UTF-8 better
env = {**os.environ}
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
# Force GBK for cmd.exe tools
env['PYTHONIOENCODING'] = 'utf-8'

# Run wechat-cli in binary mode and decode
result = subprocess.run(
    ['wechat-cli', 'sessions', '--limit', '40'],
    capture_output=True, text=False,
    env=env
)

# Try different encodings
for enc in ['utf-8', 'gbk', 'latin-1']:
    try:
        text = result.stdout.decode(enc, errors='replace')
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0:
            data = json.loads(text[start:end])
            groups = [(item['username'], item['chat']) for item in data if item.get('is_group')]
            
            # Save to JSON file for other scripts to use
            with open('D:/qwen3-asr/groups_list.json', 'w', encoding='utf-8') as f:
                json.dump(groups, f, ensure_ascii=False, indent=2)
            
            print(f'OK: {len(groups)} groups')
            for username, name in groups[:15]:
                print(f'  {username}: {name}')
            break
    except Exception as e:
        print(f'  {enc} failed: {e}')
