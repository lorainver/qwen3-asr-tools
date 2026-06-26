#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
batch_import_resume.py - 微信消息断点续传批量导入脚本

支持功能：
1. 自动获取 wechat-cli 的所有会话（群聊/私聊）
2. 维护进度状态文件 (knowledge_base/wechat/import_state.json)，支持异常退出后断点续传
3. 自动排除导入成功的会话，提供 --force 强制全部重新导入、--reset 重置进度等参数
4. 过滤会话类型：--type group (仅群聊)，--type private (仅私聊，自动排除公众号与系统占位账号)
5. 完美结合已有的去重逻辑：再次导入时先删除已有记录，保证数据一致性
6. 执行完毕后打印出各会话的数据库累计条数及时间段明细
"""

import os
import sys
import subprocess
import time
import argparse
import json
from pathlib import Path

# 确保项目根目录在 path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from wechat_db import wechat_db
from wechat_cli_importer import WeChatCliImporter
from knowledge_store import init_knowledge_base, index_document, delete_by_filename

OUTPUT_DIR = os.path.join(BASE_DIR, "knowledge_base", "wechat")
STATE_FILE = os.path.join(OUTPUT_DIR, "import_state.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_state() -> dict:
    """加载导入进度状态"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 读取状态文件失败，将重新初始化: {e}")
    return {}

def save_state(state: dict):
    """保存导入进度状态"""
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存状态文件失败: {e}")

def is_service_or_bot(session: dict) -> bool:
    """判断是否为服务号、系统内置账号或第三方机器人服务"""
    chat_name = session.get('chat', '')
    username = session.get('username', '')
    
    # 1. 明显的系统/占位/品牌服务占位账号
    system_usernames = [
        'brandsessionholder', 'brandservicesessionholder', 'filehelper', 
        'fmessage', 'newsapp', 'qqmail', 'qqsafe', 'weibo', 'tmessage',
        'mcdonalds888', 'qqwanggou001'
    ]
    if username in system_usernames:
        return True
        
    if username.startswith('gh_') or username.startswith('@') or 'openim' in username:
        return True
        
    # 2. 名字特征匹配 (过滤常见的服务号/自动助手等)
    exclude_keywords = [
        "信用卡", "银行", "航空", "安全中心", "服务", "助手", "订阅", "支付", 
        "快递", "商户", "客服", "小助手", "福利君", "管理中心", "公众号", "官方", "通知",
        "麦当劳", "肯德基", "外卖", "品牌", "购物", "京东"
    ]
    for kw in exclude_keywords:
        if kw in chat_name:
            return True
            
    return False

def get_all_sessions(limit=200) -> list:
    """获取 wechat-cli 中所有的会话"""
    print("🔍 正在获取微信会话列表...")
    try:
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run(
            ['wechat-cli', 'sessions', '--limit', str(limit)],
            capture_output=True, text=True, encoding='utf-8', env=env
        )
        if result.returncode != 0:
            print(f"❌ 获取会话列表失败: {result.stderr}")
            return []
        
        return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ 获取会话列表异常: {e}")
        return []

def import_single_session(session_info: dict, start_time: str) -> bool:
    """导入单个会话，包含全部四个步骤并自动去重"""
    chat_name = session_info['chat']
    username = session_info['username']
    is_group = session_info.get('is_group', False)
    
    print(f"\n────────────────────────────────────────────────────────────")
    print(f"🚀 正在导入: {chat_name} ({'群聊' if is_group else '私聊/公众号'})")
    print(f"   Username/Wxid: {username}")
    
    # 1. 导出为 MD 文件
    safe_name = chat_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
    raw_path = os.path.join(OUTPUT_DIR, f"{safe_name}_raw.md")
    
    cmd = [
        'wechat-cli', 'export', chat_name,
        '--format', 'markdown',
        '--start-time', start_time,
        '--output', raw_path
    ]
    
    try:
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)
        if res.returncode != 0 or not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            err = res.stderr[:200] if res.stderr else "文件为空或导出失败"
            print(f"   ❌ 导出失败: {err}")
            return False
        
        # 统计消息数量
        with open(raw_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        msg_count = len([l for l in lines if l.startswith('- [')])
        print(f"   ✅ 导出成功: {os.path.getsize(raw_path)} 字节，共计约 {msg_count} 条消息")
        
        if msg_count == 0:
            print("   ℹ️ 该时间段内无新消息，跳过后续入库步骤")
            return True
            
    except subprocess.TimeoutExpired:
        print("   ❌ 导出超时")
        return False
    except Exception as e:
        print(f"   ❌ 导出异常: {e}")
        return False
        
    # 2. 转换为标准结构化格式
    try:
        importer = WeChatCliImporter(output_dir=OUTPUT_DIR)
        std_path = importer.convert_to_standard_format(raw_path)
        print(f"   ✅ 转换标准格式成功")
    except Exception as e:
        print(f"   ❌ 格式转换失败: {e}")
        return False
        
    # 3. 导入 ChromaDB 向量知识库 (用于 RAG)
    try:
        init_knowledge_base(summarizer=None)
        category = "微信聊天记录_batch_resume"
        # 自动清理旧数据
        delete_by_filename(chat_name, category=category)
        # 重新索引
        kb_res = index_document(std_path, category=category)
        print(f"   ✅ 导入向量知识库成功 ({kb_res['chunk_count']} chunks)")
    except Exception as e:
        print(f"   ⚠️ 导入向量知识库失败 (不影响 SQLite 入库): {e}")
        
    # 4. 导入 SQLite 数据库
    try:
        # wechat_db 内部会自动执行删除旧记录再插入的逻辑以去重
        db_ok = wechat_db.import_markdown_file(raw_path, wxid_override=username)
        if db_ok:
            print(f"   ✅ SQLite 数据库入库及 FTS5 索引更新成功")
            return True
        else:
            print(f"   ❌ SQLite 数据库入库失败")
            return False
    except Exception as e:
        print(f"   ❌ SQLite 数据库入库发生异常: {e}")
        return False

def get_session_db_stats(username: str) -> dict:
    """查询该会话在数据库中的全部消息统计（包括1月9日之前的历史数据）"""
    from datetime import datetime
    try:
        cursor = wechat_db.conn.cursor()
        
        # 1. 查找 session_id
        cursor.execute("SELECT id FROM sessions WHERE wxid = ?", (username,))
        row = cursor.fetchone()
        if not row:
            return {"total": 0, "earliest": "无数据", "latest": "无数据"}
        
        session_id = row['id']
        
        # 2. 统计总数、最早和最晚时间
        cursor.execute("""
            SELECT COUNT(*) as total, 
                   MIN(create_time) as min_time, 
                   MAX(create_time) as max_time 
            FROM messages 
            WHERE session_id = ?
        """, (session_id,))
        stats = cursor.fetchone()
        
        if not stats or stats['total'] == 0:
            return {"total": 0, "earliest": "无数据", "latest": "无数据"}
            
        def format_ts(ts):
            if not ts: return "无数据"
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            
        return {
            "total": stats['total'],
            "earliest": format_ts(stats['min_time']),
            "latest": format_ts(stats['max_time'])
        }
    except Exception as e:
        return {"total": 0, "earliest": f"查询出错: {e}", "latest": "无数据"}

def main():
    epilog_text = """
使用示例 (Examples):
  1. 默认分批断点续传（本轮最多实际处理 10 个新会话，随后自动暂停）：
     python batch_import_resume.py

  2. 扩大单批处理数量（本轮最多实际处理 20 个会话）：
     python batch_import_resume.py --batch-size 20

  3. 从指定更早的日期开始导入/更新消息：
     python batch_import_resume.py --start-time 2025-12-01 --batch-size 15

  4. 强制覆盖导入（忽略已成功的进度记录，重新全量覆盖）：
     python batch_import_resume.py --force --batch-size 20

  5. 清除并重置导入进度状态，回到初始状态：
     python batch_import_resume.py --reset

  6. 仅对群聊会话进行断点续传导入（忽略私聊）：
     python batch_import_resume.py --type group --batch-size 15

  7. 仅对私聊会话进行断点续传导入（排除群聊和公众号）：
     python batch_import_resume.py --type private --batch-size 15

温馨提示 (Tips):
  - 本轮处理完成或按 Ctrl+C 中断后，下一次运行脚本会自动跳过已标记为 success 的会话。
  - 重复导入会话时，脚本内部在 SQLite 及向量知识库层均会自动执行“先删后插”，保证不重不漏。
  - 进度状态保存在: knowledge_base/wechat/import_state.json 
"""
    parser = argparse.ArgumentParser(
        description="WeChat 消息断点续传批量导入脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )
    parser.add_argument('--start-time', type=str, default="2026-01-09", help="导入消息的起始时间 (格式: YYYY-MM-DD，默认 2026-01-09)")
    parser.add_argument('--limit', type=int, default=200, help="最多读取的会话候选数量 (默认 200)")
    parser.add_argument('--batch-size', type=int, default=10, help="本次运行实际要处理(导入/更新)的会话最大数量 (默认 10)")
    parser.add_argument('--type', choices=['all', 'group', 'private'], default='all', help="过滤会话类型: all(全部), group(仅群聊), private(仅私聊，自动排除公众号与占位账号)")
    parser.add_argument('--force', action='store_true', help="强制重新导入所有会话，忽略之前的成功记录")
    parser.add_argument('--reset', action='store_true', help="清空历史导入状态，重新开始")
    args = parser.parse_args()

    if args.reset:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
        print("🗑️ 历史进度状态已重置")
        sys.exit(0)

    # 1. 获取会话列表
    raw_sessions = get_all_sessions(limit=args.limit)
    if not raw_sessions:
        print("❌ 未获取到任何会话，请确保 wechat-cli 可用并已登录微信")
        sys.exit(1)
        
    # 过滤会话类型
    if args.type == 'group':
        sessions = [s for s in raw_sessions if s.get('is_group') is True]
        type_desc = "仅群聊"
    elif args.type == 'private':
        # 仅保留真实好友的私聊（通过 is_service_or_bot 剔除所有公众号与自动化服务账号）
        sessions = [
            s for s in raw_sessions 
            if s.get('is_group') is False and not is_service_or_bot(s)
        ]
        type_desc = "仅私聊（自动排除公众号、服务号与系统账号）"
    else:
        sessions = raw_sessions
        type_desc = "全部类型"
        
    print(f"📋 共获取到 {len(raw_sessions)} 个会话候选，按类型筛选后剩余 {len(sessions)} 个会话 ({type_desc})")

    # 2. 读取状态
    state = {} if args.force else load_state()
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    processed_sessions_stats = []

    try:
        for idx, session in enumerate(sessions):
            # 检查是否已达到本次运行的批处理上限
            if (success_count + fail_count) >= args.batch_size:
                print(f"\n🛑 已达到本次运行设定的批处理上限 ({args.batch_size} 个)，程序自动停止。")
                break

            chat_name = session['chat']
            username = session['username']
            
            # 检查状态，是否需要跳过
            if username in state and state[username].get('status') == 'success':
                print(f"⏭️ [{idx + 1}/{len(sessions)}] 跳过已导入会话: {chat_name}")
                skip_count += 1
                continue
                
            # 执行导入
            ok = import_single_session(session, args.start_time)
            
            if ok:
                state[username] = {
                    "chat": chat_name,
                    "status": "success",
                    "timestamp": int(time.time()),
                    "start_time": args.start_time
                }
                success_count += 1
            else:
                state[username] = {
                    "chat": chat_name,
                    "status": "failed",
                    "timestamp": int(time.time()),
                    "start_time": args.start_time
                }
                fail_count += 1
                
            # 每次导入后实时保存状态，确保断点续传有效
            save_state(state)
            
            # 查询入库后的数据库统计数据 (包括历史数据)
            db_stats = get_session_db_stats(username)
            processed_sessions_stats.append({
                "chat": chat_name,
                "status": "成功" if ok else "失败",
                "total": db_stats["total"],
                "earliest": db_stats["earliest"],
                "latest": db_stats["latest"]
            })
            
            # 适当延时，防止高频操作导致微信被限制
            time.sleep(1.5)
            
    except KeyboardInterrupt:
        print("\n🛑 收到中断信号，程序已安全暂停。下次运行该脚本时将继续从断点处开始。")
        save_state(state)
        sys.exit(0)

    print(f"\n============================================================")
    print(f"📊 批量导入阶段性任务完成！")
    print(f"   本轮实际处理: {success_count + fail_count} 个 (上限: {args.batch_size} 个)")
    print(f"   其中成功: {success_count} 个，失败: {fail_count} 个")
    print(f"   本轮跳过(历史已成功): {skip_count} 个")
    print(f"   进度状态文件已更新至: {STATE_FILE}")

    if processed_sessions_stats:
        print(f"\n📈 本轮处理会话的数据库最新统计明细 (包含1月9日前历史数据):")
        for s in processed_sessions_stats:
            status_tag = "✅" if s["status"] == "成功" else "❌"
            print(f"  {status_tag} 【{s['chat']}】")
            print(f"     - 本次导入结果: {s['status']}")
            print(f"     - 数据库累计记录: {s['total']} 条")
            print(f"     - 消息最早时间: {s['earliest']}")
            print(f"     - 消息最晚时间: {s['latest']}")

if __name__ == '__main__':
    main()
