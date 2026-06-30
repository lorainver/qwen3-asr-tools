# -*- coding: utf-8 -*-
"""
batch_import_by_md.py - 按照 markdown 会话列表批量导入微信会话

使用说明：
1. 极速模式（只导入 SQLite 数据库，跳过向量数据库）：
   venv\Scripts\python.exe batch_import_by_md.py --batch 1 --skip-msg-db --force --skip-kb --start-time 2018-01-01

2. 后期同步模式（在空闲时，单独将已导出的标准文件索引至向量知识库）：
   venv\Scripts\python.exe batch_import_by_md.py --batch 1 --skip-msg-db --only-kb

参数说明：
  --batch <组号>       指定导入哪一组 (1-18，每组 20 个会话)
  --start <序号>       自定义起始序号
  --end <序号>         自定义结束序号
  --force              强制覆盖已导入的会话，重新从微信解密数据库中拉取历史
  --skip-msg-db        建立向量库时跳过单条消息的索引（极大提高向量化速度）
  --start-time <日期>  导出起始日期（格式 YYYY-MM-DD，默认 2020-01-01 以拉取全部历史，可设为 2018-01-01 等）
  --skip-kb            仅写入 SQLite，彻底跳过向量数据库导入
  --only-kb            仅将本地已转换好的标准 Markdown 文件同步构建向量索引，跳过微信导出和 SQLite
"""

import os
import sys
import re
import argparse
from pathlib import Path

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

from reimport_known import import_single_session, load_history, init_knowledge_base

MD_PATH = r"C:\Users\songc\.gemini\antigravity-ide\brain\ed60052d-b773-4234-b48b-33bf955b95e6\recent_sessions_analysis.md"

def parse_md_table():
    if not os.path.exists(MD_PATH):
        print(f"❌ 找不到会话列表文件: {MD_PATH}")
        return []
        
    with open(MD_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    sessions = []
    # 每一行匹配模式: | 序号 | 类型 | 会话 ID | 会话名称 | 微信 ID / 群 ID | 最早消息时间 |
    # 例如: | 1 | 私聊 | 656 | 热心市民刘女士 巴蜀美术 | `wxid_ldytgipxxvat21` | 2026-01-02 22:21:07 |
    row_pattern = re.compile(
        r'^\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([\d\-:\s]+?)\s*\|'
    )
    
    for line in lines:
        match = row_pattern.match(line)
        if match:
            seq = int(match.group(1))
            chat_type = match.group(2).strip()
            session_id = int(match.group(3))
            name = match.group(4).strip().replace('`', '')
            wxid = match.group(5).strip().replace('`', '')
            earliest_time = match.group(6).strip()
            
            # 提取日期 (YYYY-MM-DD)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', earliest_time)
            start_date = date_match.group(1) if date_match else "2026-01-09"
            
            is_group = (chat_type == "群聊")
            
            sessions.append({
                'seq': seq,
                'type': chat_type,
                'session_id': session_id,
                'name': name,
                'wxid': wxid,
                'start_date': start_date,
                'is_group': is_group,
                'raw_time': earliest_time
            })
            
    return sessions

def main():
    parser = argparse.ArgumentParser(description="按 MD 列表 20 个一组批量导入会话记录")
    parser.add_argument('--batch', type=int, help="指定导入哪一组 (1-19，每组 20 个会话)")
    parser.add_argument('--start', type=int, help="起始序号 (1-indexed)")
    parser.add_argument('--end', type=int, help="结束序号 (1-indexed, 包含)")
    parser.add_argument('--force', action='store_true', help="是否强制重新导入已存在的历史记录")
    parser.add_argument('--skip-msg-db', action='store_true', help="是否跳过生成单条消息级的向量索引")
    parser.add_argument('--start-time', type=str, default="2020-01-01", help="消息起始时间，默认 2020-01-01 以便拉取全部历史（例如2025年）")
    parser.add_argument('--skip-kb', action='store_true', help="是否彻底跳过向量知识库 (ChromaDB) 导入，仅写入 SQLite")
    parser.add_argument('--only-kb', action='store_true', help="是否仅构建向量知识库 (ChromaDB) 索引，跳过 SQLite 写入与微信导出")
    
    args = parser.parse_args()
    
    sessions = parse_md_table()
    total_sessions = len(sessions)
    if total_sessions == 0:
        print("❌ 未能成功解析任何会话列表。")
        return
        
    print(f"Total sessions parsed: {total_sessions}")
    
    # 确定导入范围
    start_idx = 1
    end_idx = total_sessions
    
    if args.batch is not None:
        batch_size = 20
        start_idx = (args.batch - 1) * batch_size + 1
        end_idx = min(args.batch * batch_size, total_sessions)
        print(f"Executing batch {args.batch}: indices {start_idx} to {end_idx}")
    elif args.start is not None and args.end is not None:
        start_idx = max(1, args.start)
        end_idx = min(args.end, total_sessions)
        print(f"Executing custom range: indices {start_idx} to {end_idx}")
    else:
        # 如果未传入任何参数，则打印说明并显示前几组的索引范围
        print("\nUsage Tips: Specify --batch <num> or --start <start> --end <end> to run.")
        print("Suggested batch distributions:")
        batch_size = 20
        num_batches = (total_sessions + batch_size - 1) // batch_size
        for b in range(1, num_batches + 1):
            s_i = (b - 1) * batch_size + 1
            e_i = min(b * batch_size, total_sessions)
            print(f"  Batch {b:2d}: --batch {b:2d}  (indices {s_i:3d} ~ {e_i:3d})")
        return
        
    # 初始化知识库
    init_knowledge_base(summarizer=None)
    history = load_history()
    
    # 运行指定范围的导入
    target_sessions = [s for s in sessions if start_idx <= s['seq'] <= end_idx]
    success_count = 0
    
    if args.only_kb:
        from reimport_known import delete_by_filename, index_document, WECHAT_DIR
        for idx, s in enumerate(target_sessions):
            print(f"\n==================================================")
            print(f"Indexing to KB: [{idx + 1}/{len(target_sessions)}] seq {s['seq']} (Session ID: {s['session_id']})")
            try:
                print(f"   Name: {s['name'].encode('gbk', 'replace').decode('gbk')}")
            except:
                print(f"   Name: {s['name'].encode('ascii', 'replace').decode('ascii')}")
            
            safe_name = s['name'].replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
            if not safe_name:
                safe_name = s['wxid'].replace('/', '_').replace('\\', '_')
            
            std_path = WECHAT_DIR / f"{safe_name}_raw.standard.md"
            if not std_path.exists():
                print(f"   [Error] Standard file not found: {std_path}")
                continue
                
            category = '微信聊天记录_wechat-cli-20260109'
            delete_by_filename(s['name'], category=category)
            print(f"   🧠 Indexing {std_path.name} to KB...")
            try:
                res = index_document(str(std_path), category=category, skip_msg_embeddings=args.skip_msg_db)
                print(f"   ✅ Done: doc_id={res['doc_id'][:8]}, chunks={res['chunk_count']}")
                success_count += 1
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                
        print(f"\n==================================================")
        print(f"Finished indexing! Success: {success_count}/{len(target_sessions)}")
        return
        
    for idx, s in enumerate(target_sessions):
        print(f"\n==================================================")
        print(f"Processing [{idx + 1}/{len(target_sessions)}] seq {s['seq']} (Session ID: {s['session_id']})")
        try:
            print(f"   Name: {s['name'].encode('gbk', 'replace').decode('gbk')}")
        except:
            print(f"   Name: {s['name'].encode('ascii', 'replace').decode('ascii')}")
        print(f"   Type: {s['type']} | WXID: {s['wxid']}")
        print(f"   Start Date: {args.start_time} (Earliest in DB: {s['raw_time']})")
        
        success = import_single_session(
            chat_name=s['name'],
            username=s['wxid'],
            is_group=s['is_group'],
            start_time=args.start_time,
            force=args.force,
            history=history,
            skip_msg_embeddings=args.skip_msg_db,
            is_incremental=False,
            skip_kb=args.skip_kb
        )
        
        if success:
            success_count += 1
            print(f"Seq {s['seq']} import SUCCESS")
        else:
            print(f"Seq {s['seq']} import FAILED")
            
    print(f"\n==================================================")
    print(f"Finished! Successfully imported {success_count}/{len(target_sessions)} sessions.")

if __name__ == '__main__':
    main()
