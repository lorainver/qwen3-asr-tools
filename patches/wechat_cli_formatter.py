"""输出格式化 — JSON (大模型友好) / Text (人类可读)"""

import json
import sys


def output_json(data, file=None):
    file = file or sys.stdout
    try:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write('\n')
    except UnicodeEncodeError:
        if hasattr(file, 'buffer'):
            serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
            file.buffer.write(serialized.encode('utf-8'))
        else:
            json.dump(data, file, ensure_ascii=True, indent=2)
            file.write('\n')


def output_text(text, file=None):
    file = file or sys.stdout
    try:
        file.write(text)
        if not text.endswith('\n'):
            file.write('\n')
    except UnicodeEncodeError:
        if hasattr(file, 'buffer'):
            file.buffer.write(text.encode('utf-8'))
            if not text.endswith('\n'):
                file.buffer.write(b'\n')
        else:
            encoded = text.encode(file.encoding, errors='replace').decode(file.encoding)
            file.write(encoded)
            if not encoded.endswith('\n'):
                file.write('\n')


def output(data, fmt='json', file=None):
    if fmt == 'json':
        output_json(data, file)
    else:
        if isinstance(data, str):
            output_text(data, file)
        elif isinstance(data, dict) and 'text' in data:
            output_text(data['text'], file)
        else:
            output_json(data, file)
