import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 检查关键函数是否存在
functions = [
    'function renderMessageContent',
    'function extractLocalId',
    'function renderImageMessage',
    'function renderVoiceMessage',
    'function renderFileMessage',
    'function renderVideoMessage',
    'function toggleVoicePlayback',
    'function formatDuration',
    'function formatFileSize',
    'function extractLinks',
    'function renderLinks',
    'wechat-image-modal',
    'wechat-voice-item',
    'wechat-file-item',
    'wechat-video-item'
]

print('Checking JavaScript functions:')
for fn in functions:
    if fn in content:
        print(f'OK: {fn}')
    else:
        print(f'MISSING: {fn}')
