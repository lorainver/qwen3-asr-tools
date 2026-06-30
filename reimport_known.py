"""
使用已知群名重新导出和导入微信会话，并支持全部会话的导出（dump）与批次导入（import）
"""
import sys, os, json, time, subprocess, argparse, threading, concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
import re

sys.path.insert(0, 'D:/qwen3-asr')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['OLLAMA_MODELS'] = 'D:\\ollama\\models'

from knowledge_store import init_knowledge_base, index_document, get_vectorstore, DOCS_PATH, delete_by_filename
from wechat_db import wechat_db
from wechat_cli_importer import WeChatCliImporter

db_lock = threading.Lock()


# 历史记录和目录定义
HISTORY_FILE = Path("D:/qwen3-asr/import_history.json")
WECHAT_DIR = Path("D:/qwen3-asr/knowledge_base/wechat")

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'utf-8'
        try:
            print(msg.encode(enc, errors='replace').decode(enc))
        except Exception:
            try:
                print(msg.encode('gbk', errors='replace').decode('gbk'))
            except Exception:
                print(msg.encode('ascii', errors='replace').decode('ascii'))

def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            safe_print(f"读取历史记录失败，重新创建: {e}")
    return {}

def save_history(history):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        safe_print(f"保存历史记录失败: {e}")

def load_exclude_list():
    exclude_file = Path("D:/qwen3-asr/exclude_sessions.json")
    default_exclude = {
        "usernames": [
            "@placeholder_foldgroup",
            "brandsessionholder",
            "cmb4008205555",
            "brandservicesessionholder",
            "notifymessage",
            "qqwanggou001",
            "weixin",
            "wxid_t5t60oy4syhv11",
            "qqsafe",
            "@opencustomerservicemsg",
            "mcdonalds888",
            "xingbakezhongguo"
        ],
        "suffixes": [
            "@openim",
            "@kefu.openim"
        ]
    }
    if not exclude_file.exists():
        try:
            with open(exclude_file, 'w', encoding='utf-8') as f:
                json.dump(default_exclude, f, ensure_ascii=False, indent=2)
        except Exception as e:
            safe_print(f"创建默认排除列表失败: {e}")
        return default_exclude
    else:
        try:
            with open(exclude_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            safe_print(f"读取排除列表失败: {e}")
            return default_exclude

def should_exclude(username, exclude_config):
    if username.startswith("gh_"):
        return True
    
    usernames = exclude_config.get("usernames", [])
    if username in usernames:
        return True
        
    suffixes = exclude_config.get("suffixes", [])
    for suffix in suffixes:
        if username.endswith(suffix):
            return True
            
    return False

def dump_sessions():
    safe_print("=== 正在导出全部微信群聊和私聊 ===")
    exclude_config = load_exclude_list()
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    try:
        r = subprocess.run(
            ['wechat-cli', 'sessions', '--limit', '10000'],
            capture_output=True, text=True, encoding='utf-8', env=env
        )
        if r.returncode != 0:
            safe_print(f"导出失败: {r.stderr}")
            return
        
        sessions = json.loads(r.stdout)
        groups = []
        privates = []
        
        for s in sessions:
            username = s.get("username", "")
            if should_exclude(username, exclude_config):
                continue
            
            item = {
                "chat": s.get("chat"),
                "username": username,
                "is_group": s.get("is_group", False)
            }
            if s.get("is_group", False):
                groups.append(item)
            else:
                privates.append(item)
        
        # 保存到 JSON
        with open("all_groups.json", "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        with open("all_privates.json", "w", encoding="utf-8") as f:
            json.dump(privates, f, ensure_ascii=False, indent=2)
            
        safe_print(f"成功导出 {len(groups)} 个群聊 到 all_groups.json")
        safe_print(f"成功导出 {len(privates)} 个私聊/公众号 到 all_privates.json")
    except Exception as e:
        safe_print(f"导出过程中发生异常: {e}")

def clear_knowledge_base():
    safe_print("=== 正在清空知识库 ===")
    init_knowledge_base(summarizer=None)
    vs = get_vectorstore()
    all_ids = vs.collection.get(limit=10000)
    if all_ids['ids']:
        vs.collection.delete(ids=all_ids['ids'])
    index_file = DOCS_PATH.parent / 'index.json'
    if index_file.exists():
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    safe_print("KB 清空完成")


def parse_raw_md(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    messages = []
    current_msg = None
    msg_pattern = re.compile(r'^- \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (.*?): (.*)')
    
    for line in lines:
        line_str = line.rstrip('\n')
        match = msg_pattern.match(line_str)
        if match:
            if current_msg:
                messages.append(current_msg)
            time_str = match.group(1)
            try:
                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            except Exception:
                dt = datetime.min
            current_msg = {
                "dt": dt,
                "raw_lines": [line_str]
            }
        else:
            if current_msg:
                current_msg["raw_lines"].append(line_str)
    if current_msg:
        messages.append(current_msg)
    return messages

def merge_and_save_raw_md(old_path, new_path, output_path, chat_name, is_group):
    old_msgs = parse_raw_md(old_path)
    new_msgs = parse_raw_md(new_path)
    
    if not new_msgs:
        merged_msgs = old_msgs
    elif not old_msgs:
        merged_msgs = new_msgs
    else:
        t_min = min(m["dt"] for m in new_msgs)
        merged_msgs = [m for m in old_msgs if m["dt"] < t_min] + new_msgs
        
    header = [
        f"# 聊天记录: {chat_name}",
        "",
        "**时间范围:** 最早 ~ 最新",
        "",
        f"**导出时间:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"**消息数量:** {len(merged_msgs)}",
        "",
        f"**类型:** {'群聊' if is_group else '私聊'}",
        "",
        "---",
        ""
    ]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(header))
        for msg in merged_msgs:
            f.write("\n".join(msg["raw_lines"]) + "\n")
            
    return len(merged_msgs)

def import_single_session(chat_name, username, is_group, start_time, force=False, history=None, export_limit=100000, skip_msg_embeddings=False, is_incremental=False, skip_kb=False):
    if history is None:
        history = {}
        
    safe_name = chat_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
    if not safe_name:
        safe_name = username.replace('/', '_').replace('\\', '_')
    
    if not force and not is_incremental and username in history:
        safe_print(f"[跳过] 会话 '{chat_name}' ({username}) 已于 {history[username].get('last_import_time')} 导入成功，自动跳过。")
        return True
        
    WECHAT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = WECHAT_DIR / f"{safe_name}_raw.md"
    std_path = WECHAT_DIR / f"{safe_name}_raw.standard.md"
    
    do_merge = is_incremental and raw_path.exists()
    export_path = WECHAT_DIR / f"{safe_name}_raw.temp.md" if do_merge else raw_path
    
    mode_desc = "【增量更新模式】" if do_merge else "【首次全量导入】"
    safe_print(f"\n[执行中] 正在导出与导入会话: {chat_name} ({username}) {mode_desc}")
    safe_print(f"  -> 导出起始日期: {start_time}")
    
    # 导出
    cmd = [
        'wechat-cli',
        'export',
        '--format', 'markdown',
        '--start-time', start_time,
        '--limit', str(export_limit),
        '--output', str(export_path),
        '--',
        username
    ]
    
    try:
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        r = subprocess.run(cmd, capture_output=True, text=False, timeout=120, env=env)
        
        if r.returncode != 0 or not export_path.exists() or export_path.stat().st_size == 0:
            if do_merge and export_path.exists():
                try: export_path.unlink()
                except: pass
            stderr_text = r.stderr.decode('utf-8', errors='replace').strip()
            # 如果是正常完成没有消息记录，wechat-cli 的错误输出会包含 "无消息记录"
            if "无消息记录" in stderr_text:
                safe_print(f"  -> ℹ️ 微信数据库在该时间段内没有任何新消息记录。")
                with db_lock:
                    # 更新历史导入时间，防止下次重复扫描无新消息的日期
                    history[username] = {
                        "chat": chat_name,
                        "is_group": is_group,
                        "last_import_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "msg_count": history[username].get("msg_count", 0) if username in history else 0
                    }
                    save_history(history)
                return True
            else:
                safe_print(f"  -> ❌ 微信消息导出失败 (错误码={r.returncode}): {stderr_text[:200]}")
                return False
            
        # 统计消息行数/条数
        with open(export_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        msg_count = len([l for l in lines if l.startswith('- [')])
        safe_print(f"  -> 📥 微信导出成功: 文件大小 {export_path.stat().st_size} 字节，拉取到约 {msg_count} 条消息")
        
        with db_lock:
            # 导入 SQLite
            safe_print(f"  -> 💾 正在写入本地 SQLite 数据库 (去重处理中)...")
            db_ok = wechat_db.import_markdown_file(str(export_path), wxid_override=username)
            if db_ok:
                safe_print(f"  -> 💾 数据库写入成功。")
                try:
                    # 增量提取干货资源并写入数据库
                    from chat_analytics import ChatAnalytics
                    analytics = ChatAnalytics()
                    res_count = analytics.extract_session_resources(username)
                    safe_print(f"  -> 📦 自动提取新资源: 成功导入 {res_count} 个干货资源")
                except Exception as e:
                    safe_print(f"  [Warning] 自动提取干货资源失败: {e}")
            else:
                safe_print(f"  -> ❌ 数据库写入失败！")
                
            if do_merge:
                safe_print(f"  -> 📝 正在与本地历史 Markdown 文件进行物理合并去重...")
                merged_msg_count = merge_and_save_raw_md(raw_path, export_path, raw_path, chat_name, is_group)
                safe_print(f"  -> 📝 合并完成！合并后总计 {merged_msg_count} 条聊天记录")
                try: export_path.unlink()
                except: pass
                msg_count_history = merged_msg_count
            else:
                msg_count_history = msg_count
                
            # 转换格式 (转换合并后的完整 raw_path)
            importer = WeChatCliImporter(output_dir=str(WECHAT_DIR))
            std_output_path = importer.convert_to_standard_format(str(raw_path))
            
            # 导入 KB
            if not skip_kb:
                category = '微信聊天记录_wechat-cli-20260109'
                delete_by_filename(chat_name, category=category)
                safe_print(f"  -> 🧠 正在重新分块并索引至向量知识库...")
                result = index_document(std_output_path, category=category, skip_msg_embeddings=skip_msg_embeddings)
                safe_print(f"  -> 🧠 向量知识库更新成功: 块ID={result['doc_id'][:8]}, 生成切片={result['chunk_count']} 个")
            else:
                safe_print(f"  -> 🧠 已选择跳过向量知识库导入。")
            
            # 记录历史
            history[username] = {
                "chat": chat_name,
                "is_group": is_group,
                "last_import_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "msg_count": msg_count_history
            }
            save_history(history)
        return True
        
    except subprocess.TimeoutExpired:
        safe_print(f"  [Error] Export timed out!")
        return False
    except Exception as e:
        safe_print(f"  [Error] Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="微信会话批量导入与增量更新工具")
    parser.add_argument('--dump', action='store_true', help="【导出模式】从本地微信导出所有群聊和私聊会话列表至 JSON 文件")
    parser.add_argument('--file', type=str, help="【批量导入/更新模式】指定需要处理的会话 JSON 文件（如 all_groups.json 或 all_privates.json）")
    parser.add_argument('--limit-sessions', type=int, default=0, help="限制本次成功导入/更新的最大会话数（0 表示无限制）")
    parser.add_argument('--start-time', type=str, default="2026-01-09", help="消息起始时间（格式 YYYY-MM-DD，默认 2026-01-09；在增量模式下，不指定此项则默认自动推算）")
    parser.add_argument('--export-limit', type=int, default=100000, help="单次会话导出最大消息数，默认 100000")
    parser.add_argument('--skip-msg-db', action='store_true', help="跳过生成单条消息级的向量索引（极速提升导入速度，大群聊建议开启）")
    parser.add_argument('--clear-kb', action='store_true', help="导入前清空向量知识库（慎用）")
    parser.add_argument('--force', action='store_true', help="强制重新导入，即便已经在历史记录中（重新拉取全量历史）")
    parser.add_argument('--update', action='store_true', help="【增量更新模式】对已有记录进行更新。默认从该会话上次导入时间前推 2 天拉取新消息，并在物理 Markdown 文件与 SQLite 数据库中进行去重合并")
    parser.add_argument('--workers', type=int, default=1, help="并发工作线程数（针对批量导入，建议设为 4-8 以极速导出）")
    
    args = parser.parse_args()
    
    # 1. 导出模式
    if args.dump:
        dump_sessions()
        return
        
    # 2. 批量导入模式
    if args.file:
        file_path = Path(args.file)
        if file_path.name in ["all_groups.json", "all_privates.json"]:
            safe_print(f"🔄 检测到使用标准会话文件 '{file_path.name}'，正在自动拉取本地微信最新会话列表并进行过滤更新...")
            dump_sessions()
            safe_print(f"✅ 微信最新会话列表自动拉取与排重过滤已完成！\n")
            
        if not os.path.exists(args.file):
            safe_print(f"[Error] Can't find file: {args.file}")
            sys.exit(1)
            
        with open(args.file, 'r', encoding='utf-8') as f:
            sessions = json.load(f)
            
        safe_print(f"=== 批次导入与更新模式: 从 {args.file} 读取了 {len(sessions)} 个过滤后的干净会话 ===")
        if args.clear_kb:
            clear_knowledge_base()
            
        # 初始化知识库
        init_knowledge_base(summarizer=None)
        
        history = load_history()
        exclude_config = load_exclude_list()
        
        # 预先过滤真正需要导入的会话，以便应用 limit 限制和并行调度
        sessions_to_import = []
        for s in sessions:
            username = s.get('username')
            if should_exclude(username, exclude_config):
                continue
            if not args.force and not args.update and username in history:
                continue
            sessions_to_import.append(s)
            
        if args.limit_sessions > 0:
            sessions_to_import = sessions_to_import[:args.limit_sessions]
            
        total_to_import = len(sessions_to_import)
        safe_print(f"📄 本次排重过滤后，实际需要导入/更新的会话数: {total_to_import} 个")
        
        if total_to_import == 0:
            safe_print("ℹ️ 所有会话均已导入，无需更新。")
            return
            
        imported_count = 0
        
        if args.workers > 1:
            safe_print(f"🚀 启用多线程模式，工作线程数: {args.workers}")
            futures_map = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                for idx, s in enumerate(sessions_to_import):
                    chat_name = s.get('chat')
                    username = s.get('username')
                    is_group = s.get('is_group', False)
                    
                    # 计算起始时间与是否为增量模式
                    session_start_time = args.start_time
                    is_incremental = False
                    if args.update and username in history:
                        is_incremental = True
                        if args.start_time == "2026-01-09":
                            last_time_str = history[username].get('last_import_time')
                            if last_time_str:
                                try:
                                    last_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                                    session_start_time = (last_dt - timedelta(days=2)).strftime("%Y-%m-%d")
                                except Exception:
                                    pass
                                    
                    future = executor.submit(
                        import_single_session,
                        chat_name=chat_name,
                        username=username,
                        is_group=is_group,
                        start_time=session_start_time,
                        force=args.force,
                        history=history,
                        export_limit=args.export_limit,
                        skip_msg_embeddings=args.skip_msg_db,
                        is_incremental=is_incremental
                    )
                    futures_map[future] = chat_name
                    
                for idx, future in enumerate(concurrent.futures.as_completed(futures_map)):
                    chat_name = futures_map[future]
                    try:
                        success = future.result()
                        if success:
                            imported_count += 1
                        safe_print(f"  [{idx + 1} / {total_to_import}] 会话 '{chat_name}' 处理完成 (成功数={imported_count})")
                    except Exception as e:
                        safe_print(f"  [{idx + 1} / {total_to_import}] 会话 '{chat_name}' 出现未捕获异常: {e}")
        else:
            for idx, s in enumerate(sessions_to_import):
                chat_name = s.get('chat')
                username = s.get('username')
                is_group = s.get('is_group', False)
                
                # 计算起始时间与是否为增量模式
                session_start_time = args.start_time
                is_incremental = False
                if args.update and username in history:
                    is_incremental = True
                    if args.start_time == "2026-01-09":
                        last_time_str = history[username].get('last_import_time')
                        if last_time_str:
                            try:
                                last_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                                session_start_time = (last_dt - timedelta(days=2)).strftime("%Y-%m-%d")
                            except Exception:
                                pass
                
                safe_print(f"\n进度: [{idx + 1} / {total_to_import}]")
                success = import_single_session(
                    chat_name=chat_name,
                    username=username,
                    is_group=is_group,
                    start_time=session_start_time,
                    force=args.force,
                    history=history,
                    export_limit=args.export_limit,
                    skip_msg_embeddings=args.skip_msg_db,
                    is_incremental=is_incremental
                )
                if success:
                    imported_count += 1
                    
        safe_print(f"\n=== 导入完成: 本次共导入 {imported_count} 个会话 ===")
        return

    # 3. 默认/旧的群聊重新导入模式
    safe_print("=== 默认模式: 重新导入已知群聊 ===")
    TARGET_GROUPS = [
        '南岸中小学二手闲置',
        '米妈家长圈闲置2群',
        '4-5年级上岸政策活动群',
        '重庆大学MBA总群(2)',
        '金佛山-良瑜业主3群',
        '果妈思维小初宝藏群（米妈定制）',
        '💪信竞家长交流群',
        '数学竞赛家长交流群（小雅）',
        '欣怡宝贝外贸童装1⃣ 群',
    ]
    
    if args.clear_kb:
        clear_knowledge_base()
    else:
        clear_knowledge_base()
        
    init_knowledge_base(summarizer=None)
    history = load_history()
    
    for i, group_name in enumerate(TARGET_GROUPS):
        import_single_session(
            chat_name=group_name,
            username=group_name,
            is_group=True,
            start_time=args.start_time,
            force=True,
            history=history,
            export_limit=args.export_limit,
            skip_msg_embeddings=args.skip_msg_db,
            is_incremental=False
        )
        
if __name__ == '__main__':
    main()
