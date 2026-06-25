#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wechat_importer.py - 通用微信会话记录导入工具

功能：
1. 自动调用 wechat-cli 导出任意指定会话的聊天记录为 Markdown 文件
2. 自动转换为标准格式并导入 ChromaDB 向量知识库
3. 自动解析入库到 SQLite 结构化数据库 (D:/Work/Useful_Tools/chat_record_analyzer/data/chat_records.db)
"""

import os
import sys
import subprocess
import time
import argparse
import json

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 设置编码环境变量，防止 Windows 控制台乱码
os.environ['PYTHONIOENCODING'] = 'utf-8'

from wechat_db import wechat_db
from wechat_cli_importer import WeChatCliImporter
from knowledge_store import init_knowledge_base, index_document, delete_by_filename

OUTPUT_DIR = os.path.join(BASE_DIR, "knowledge_base", "wechat")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def find_session_by_name(chat_name):
    """通过 wechat-cli sessions 查找匹配的会话，获取准确的名称和用户名"""
    print(f"🔍 正在检索 wechat-cli 会话列表以匹配: '{chat_name}'...")
    try:
        # 强制使用 UTF-8 编码读取 wechat-cli 输出
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run(
            ['wechat-cli', 'sessions', '--limit', '100'],
            capture_output=True, text=True, encoding='utf-8', env=env
        )
        if result.returncode != 0:
            print(f"❌ 检索会话列表失败: {result.stderr}")
            return None
        
        sessions = json.loads(result.stdout)
        
        # 模糊匹配
        matches = []
        for s in sessions:
            if chat_name.lower() in s['chat'].lower() or chat_name.lower() in s['username'].lower():
                matches.append(s)
                
        if not matches:
            return None
            
        if len(matches) == 1:
            return matches[0]
            
        print(f"⚠️ 匹配到多个会话，请选择一个:")
        for idx, m in enumerate(matches):
            print(f"  [{idx + 1}] {m['chat']} ({'群聊' if m['is_group'] else '私聊'}) - Username: {m['username']}")
            
        choice = input("请输入对应的序号 (默认 1): ").strip()
        choice_idx = int(choice) - 1 if choice.isdigit() else 0
        if 0 <= choice_idx < len(matches):
            return matches[choice_idx]
        return matches[0]
        
    except Exception as e:
        print(f"⚠️ 匹配会话时发生异常: {e}")
        # 如果出错了，直接返回用户输入的原始名称
        return {"chat": chat_name, "username": chat_name, "is_group": False}

def import_session(chat_name, start_time="2026-01-09"):
    # 1. 查找真实会话
    session_info = find_session_by_name(chat_name)
    if not session_info:
        print(f"❌ 未找到匹配的微信会话: '{chat_name}'，请检查名称是否正确！")
        return False
        
    real_chat_name = session_info['chat']
    username = session_info['username']
    is_group = session_info.get('is_group', False)
    
    print(f"\n🚀 开始导入会话:")
    print(f"   会话名称: {real_chat_name}")
    print(f"   微信用户名: {username}")
    print(f"   会话类型: {'群聊' if is_group else '私聊/公众号'}")
    print(f"   起始时间: {start_time}")
    
    # 2. 导出为 Markdown 文件
    safe_name = real_chat_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
    raw_path = os.path.join(OUTPUT_DIR, f"{safe_name}_raw.md")
    
    cmd = [
        'wechat-cli',
        'export',
        real_chat_name,
        '--format', 'markdown',
        '--start-time', start_time,
        '--output', raw_path
    ]
    
    print(f"📤 [1/4] 正在从微信导出为 Markdown...")
    try:
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
        if res.returncode != 0 or not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            err = res.stderr[:300] if res.stderr else "文件为空或导出失败"
            print(f"   ❌ 导出失败: {err}")
            return False
            
        # 统计消息数量
        with open(raw_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        msg_count = len([l for l in lines if l.startswith('- [')])
        print(f"   ✅ 导出成功: {os.path.getsize(raw_path)} 字节，共计约 {msg_count} 条消息")
        
    except Exception as e:
        print(f"   ❌ 导出过程中发生异常: {e}")
        return False
        
    # 3. 转换为标准结构化格式
    print(f"🔄 [2/4] 正在对 Markdown 进行标准格式转换...")
    try:
        importer = WeChatCliImporter(output_dir=OUTPUT_DIR)
        std_path = importer.convert_to_standard_format(raw_path)
        print(f"   ✅ 转换成功: {os.path.basename(std_path)}")
    except Exception as e:
        print(f"   ❌ 转换失败: {e}")
        return False
        
    # 4. 导入 ChromaDB 向量知识库 (用于 RAG 对话)
    print(f"📚 [3/4] 正在导入 ChromaDB 向量知识库...")
    try:
        # 只初始化一次
        init_knowledge_base(summarizer=None)
        category = "微信聊天记录_manual_import"
        
        # 清除旧向量
        delete_by_filename(real_chat_name, category=category)
        
        # 重新索引
        kb_res = index_document(std_path, category=category)
        print(f"   ✅ 知识库导入成功: {kb_res['chunk_count']} 个文本块 (ID: {kb_res['doc_id']})")
    except Exception as e:
        print(f"   ❌ 知识库导入发生异常: {e}")
        
    # 5. 导入 SQLite 结构化检索数据库
    print(f"📊 [4/4] 正在导入 SQLite 数据库 (D:/Work/Useful_Tools/chat_record_analyzer/data/chat_records.db)...")
    try:
        # import_markdown_file 解析 raw 格式 md，并在内部写入 sessions, users, messages 表并触发 FTS5
        db_ok = wechat_db.import_markdown_file(raw_path, wxid_override=username)
        if db_ok:
            print(f"   ✅ SQLite 数据库导入成功！会话已入库，全文检索索引已更新。")
            return True
        else:
            print(f"   ❌ SQLite 数据库导入失败。")
            return False
    except Exception as e:
        print(f"   ❌ SQLite 数据库导入发生异常: {e}")
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="WeChat 会话导入工具")
    parser.add_argument('chat', type=str, help="要导出的群聊或私聊显示名称 (支持模糊匹配)")
    parser.add_argument('--start-time', type=str, default="2026-01-09", help="消息起始时间 (格式: YYYY-MM-DD，默认 2026-01-09)")
    
    # 交互式引导
    if len(sys.argv) == 1:
        print("💡 微信聊天记录通用导入工具 (交互式模式)")
        chat = input("请输入要导入的群聊名称或私聊好友备注: ").strip()
        if not chat:
            print("❌ 名称不能为空！")
            sys.exit(1)
        start = input("请输入导出起始日期 (默认 2026-01-09): ").strip()
        if not start:
            start = "2026-01-09"
        import_session(chat, start)
    else:
        args = parser.parse_args()
        import_session(args.chat, args.start_time)
