import sqlite3

conn = sqlite3.connect('D:/qwen3-asr/knowledge_base/wechat_chat_records.db')
cursor = conn.cursor()

# 统计各种消息类型
types = [
    ('图片', '%[图片]%'),
    ('文件', '%[文件]%'),
    ('语音', '%[语音]%'),
    ('视频', '%[视频]%'),
    ('链接', '%http%'),
]

print('消息类型统计:')
total = 0
for name, pattern in types:
    cursor.execute('SELECT COUNT(*) FROM messages WHERE content LIKE ?', (pattern,))
    count = cursor.fetchone()[0]
    print(f'  {name}: {count}条')
    total += count

cursor.execute('SELECT COUNT(*) FROM messages')
all_count = cursor.fetchone()[0]
print(f'  文本: {all_count - total}条')
print(f'  总计: {all_count}条')

# 查看语音消息样本
print('\n语音消息样本:')
cursor.execute("SELECT content FROM messages WHERE content LIKE '%[语音]%' LIMIT 3")
voice = cursor.fetchall()
for v in voice:
    print(f'  - {v[0]}')

# 查看视频消息样本
print('\n视频消息样本:')
cursor.execute("SELECT content FROM messages WHERE content LIKE '%[视频]%' LIMIT 3")
video = cursor.fetchall()
for v in video:
    print(f'  - {v[0]}')

# 查看链接消息样本
print('\n链接消息样本:')
cursor.execute("SELECT content FROM messages WHERE content LIKE '%http%' LIMIT 3")
links = cursor.fetchall()
for l in links:
    print(f'  - {l[0][:100]}...')

conn.close()
