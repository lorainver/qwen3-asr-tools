import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class WechatDatabaseManager:
    def __init__(self, db_path: str = "D:/Work/Useful_Tools/chat_record_analyzer/data/chat_records.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # 启用 WAL 模式，提高并发性能
        self.conn.execute("PRAGMA journal_mode=WAL;")
        # 调整缓存大小，提高查询性能
        self.conn.execute("PRAGMA cache_size=-64000;")  # 64MB
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wxid TEXT UNIQUE NOT NULL,
                nickname TEXT,
                remark TEXT,
                display_name TEXT,
                type TEXT,
                last_timestamp INTEGER,
                message_count INTEGER,
                file_name TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                avatar_base64 TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                local_id INTEGER,
                create_time INTEGER,
                formatted_time TEXT,
                type TEXT,
                local_type INTEGER,
                content TEXT,
                is_send INTEGER,
                sender_username TEXT,
                sender_display_name TEXT,
                source TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (sender_username) REFERENCES users(username)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_sender_username ON messages(sender_username)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_sender_display_name ON messages(sender_display_name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_create_time ON messages(create_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, create_time)
        """)

        # FTS5 virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                sender_display_name,
                message_id,
                content="messages",
                content_rowid="id"
            )
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content, sender_display_name)
                VALUES (new.id, new.content, new.sender_display_name);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
                INSERT INTO messages_fts(rowid, content, sender_display_name)
                VALUES (new.id, new.content, new.sender_display_name);
            END
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                group_name TEXT NOT NULL,
                wxid TEXT NOT NULL,
                wechat_name TEXT,
                nickname TEXT,
                join_time TEXT,
                inviter TEXT,
                message_count INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(group_name, wxid)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_group_members_wxid ON group_members(wxid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_name)")

        self.conn.commit()

    def insert_session(self, session_data: Dict, file_name: str) -> int:
        cursor = self.conn.cursor()
        wxid = session_data.get("wxid")
        
        # 检查是否已存在该 wxid 的会话
        cursor.execute("SELECT id FROM sessions WHERE wxid = ?", (wxid,))
        row = cursor.fetchone()
        if row:
            session_id = row['id']
            # 如果存在，则更新数据（保留原始 id，防止产生孤儿消息数据）
            cursor.execute("""
                UPDATE sessions SET 
                    nickname = ?, remark = ?, display_name = ?, type = ?, 
                    last_timestamp = ?, message_count = ?, file_name = ?
                WHERE id = ?
            """, (
                session_data.get("nickname"),
                session_data.get("remark"),
                session_data.get("displayName"),
                session_data.get("type"),
                session_data.get("lastTimestamp"),
                session_data.get("messageCount"),
                file_name,
                session_id
            ))
        else:
            # 如果不存在，则正常插入新记录
            cursor.execute("""
                INSERT INTO sessions 
                (wxid, nickname, remark, display_name, type, last_timestamp, message_count, file_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wxid,
                session_data.get("nickname"),
                session_data.get("remark"),
                session_data.get("displayName"),
                session_data.get("type"),
                session_data.get("lastTimestamp"),
                session_data.get("messageCount"),
                file_name
            ))
            session_id = cursor.lastrowid
            
        self.conn.commit()
        return session_id

    def insert_user(self, username: str, display_name: str, avatar_base64: Optional[str] = None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (username, display_name, avatar_base64)
            VALUES (?, ?, ?)
        """, (username, display_name, avatar_base64))
        self.conn.commit()

    def insert_message(self, session_id: int, message_data: Dict):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO messages 
            (session_id, local_id, create_time, formatted_time, type, local_type, 
             content, is_send, sender_username, sender_display_name, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            message_data.get("localId"),
            message_data.get("createTime"),
            message_data.get("formattedTime"),
            message_data.get("type"),
            message_data.get("localType"),
            message_data.get("content"),
            message_data.get("isSend"),
            message_data.get("senderUsername"),
            message_data.get("senderDisplayName"),
            message_data.get("source")
        ))
        self.conn.commit()

    def search_by_username(self, username: str, limit: int = 10, offset: int = 0) -> Dict:
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT s.id, s.wxid, s.display_name, s.type, s.file_name, COUNT(m.id) as msg_count
            FROM sessions s
            INNER JOIN messages m ON s.id = m.session_id
            WHERE m.sender_username LIKE ? OR m.sender_display_name LIKE ?
            GROUP BY s.id
            ORDER BY s.last_timestamp DESC
        """, (f"%{username}%", f"%{username}%"))
        sessions = [dict(row) for row in cursor.fetchall()]
        
        results = []
        for session in sessions:
            if limit > 0:
                cursor.execute("""
                    SELECT m.id, m.content, m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    WHERE m.session_id = ? AND (m.sender_username LIKE ? OR m.sender_display_name LIKE ?)
                    ORDER BY m.create_time DESC
                    LIMIT ? OFFSET ?
                """, (session['id'], f"%{username}%", f"%{username}%", limit, offset))
                messages = [dict(row) for row in cursor.fetchall()]
            else:
                cursor.execute("""
                    SELECT m.id, m.content, m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    WHERE m.session_id = ? AND (m.sender_username LIKE ? OR m.sender_display_name LIKE ?)
                    ORDER BY m.create_time DESC
                """, (session['id'], f"%{username}%", f"%{username}%"))
                messages = [dict(row) for row in cursor.fetchall()]
            
            results.append({
                'session': session,
                'messages': messages,
                'total_count': session['msg_count']
            })
        
        total_messages = sum(session['msg_count'] for session in sessions)
        session_stats = [
            {
                'id': session['id'],
                'name': session['display_name'],
                'count': session['msg_count']
            }
            for session in sessions
        ]
        
        cursor.execute("""
            SELECT m.sender_display_name, COUNT(*) as count
            FROM messages m
            WHERE m.sender_username LIKE ? OR m.sender_display_name LIKE ?
            GROUP BY m.sender_display_name
            ORDER BY count DESC
        """, (f"%{username}%", f"%{username}%"))
        sender_stats = [dict(row) for row in cursor.fetchall()]
        
        return {
            'results': results,
            'total': len(results),
            'total_messages': total_messages,
            'session_stats': session_stats,
            'sender_stats': sender_stats
        }

    def search_by_keyword(self, keyword: str, session_id: Optional[int] = None, sender_display_name: Optional[str] = None, context_lines: int = 3, limit: int = 50, offset: int = 0, filters: Optional[List[str]] = None, sort_by: str = "time", sort_order: str = "desc", start_time: Optional[int] = None, end_time: Optional[int] = None, show_context: bool = False, only_sender: bool = False, session_type: Optional[str] = None) -> Dict:
        import re
        
        cursor = self.conn.cursor()
        
        # 默认屏蔽群或用户（可为空）
        BLOCKED_SESSIONS = []
        BLOCKED_USERS = []
        
        # 处理过滤参数
        final_filters = filters if filters is not None else []
        
        # 构建SQL查询
        if only_sender:
            base_query = """
                SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                       m.sender_display_name, m.formatted_time, m.create_time
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                WHERE 1=1
            """
            params = []
        else:
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in keyword)
            
            if has_chinese:
                base_query = """
                    SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.content LIKE ?
                """
                params = [f"%{keyword}%"]
            else:
                base_query = """
                    SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.id IN (
                        SELECT rowid FROM messages_fts 
                        WHERE messages_fts MATCH ?
                    )
                """
                params = [keyword]
        
        if session_id:
            base_query += " AND m.session_id = ?"
            params.append(session_id)

        if session_type and session_type != '全部':
            base_query += " AND s.type = ?"
            params.append(session_type)
        
        if sender_display_name:
            # 尝试通过 group_members 映射微信ID和所有可能的群昵称/微信号
            cursor.execute("""
                SELECT DISTINCT wechat_name, nickname, wxid 
                FROM group_members 
                WHERE wxid = ? OR wechat_name = ? OR nickname = ?
            """, (sender_display_name, sender_display_name, sender_display_name))
            associated_rows = cursor.fetchall()
            
            names_to_match = {sender_display_name}
            for row in associated_rows:
                if row["wechat_name"]:
                    names_to_match.add(row["wechat_name"])
                if row["nickname"]:
                    names_to_match.add(row["nickname"])
                if row["wxid"]:
                    names_to_match.add(row["wxid"])
            
            match_clauses = []
            for name in names_to_match:
                match_clauses.append("m.sender_display_name LIKE ?")
                match_clauses.append("m.sender_username LIKE ?")
                params.append(f"%{name}%")
                params.append(f"%{name}%")
            
            base_query += f" AND ({' OR '.join(match_clauses)})"
        
        if start_time:
            base_query += " AND m.create_time >= ?"
            params.append(start_time)
        if end_time:
            base_query += " AND m.create_time <= ?"
            params.append(end_time)
        
        order_clause = ""
        if sort_by == "session":
            order_clause = " ORDER BY s.display_name"
            if sort_order.lower() == "desc":
                order_clause += " DESC"
            else:
                order_clause += " ASC"
            order_clause += ", m.create_time"
            if sort_order.lower() == "desc":
                order_clause += " DESC"
            else:
                order_clause += " ASC"
        else:
            order_clause = " ORDER BY m.create_time"
            if sort_order.lower() == "desc":
                order_clause += " DESC"
            else:
                order_clause += " ASC"
        
        base_query += order_clause
        cursor.execute(base_query, params)
        all_matches = [dict(row) for row in cursor.fetchall()]
        
        filtered_matches = []
        for match in all_matches:
            should_filter = False
            for filter_pattern in final_filters:
                try:
                    if re.search(filter_pattern, match['content']):
                        should_filter = True
                        break
                except re.error:
                    if filter_pattern in match['content']:
                        should_filter = True
                        break
            
            if not should_filter and BLOCKED_SESSIONS:
                if match['session_name'] in BLOCKED_SESSIONS or str(match['session_id']) in BLOCKED_SESSIONS:
                    should_filter = True
            
            if not should_filter and BLOCKED_USERS:
                if match['sender_display_name'] in BLOCKED_USERS:
                    should_filter = True
            
            if not should_filter:
                filtered_matches.append(match)
        
        total_results = len(filtered_matches)
        
        if limit > 0:
            paginated_results = filtered_matches[offset:offset + limit]
        else:
            paginated_results = filtered_matches[offset:]
        
        if show_context:
            for result in paginated_results:
                result["context"] = self.get_message_context(result["id"], context_lines, filters=final_filters)
        else:
            for result in paginated_results:
                result["context"] = {"before": [], "after": []}
        
        session_stats = {}
        sender_stats = {}
        
        # 统计: 按会话
        for match in filtered_matches:
            if match['session_id']:
                session_key = f"{match['session_id']}-{match['session_name']}"
                if session_key not in session_stats:
                    session_stats[session_key] = {
                        'id': match['session_id'],
                        'name': match['session_name'],
                        'type': match.get('session_type', ''),
                        'count': 0
                    }
                session_stats[session_key]['count'] += 1

        # 统计: 按聊天类型 (群聊/私聊/公众号)
        type_stats = {}
        for match in filtered_matches:
            t = match.get('session_type') or '未知'
            if t not in type_stats:
                type_stats[t] = 0
            type_stats[t] += 1
            
            if match['sender_display_name']:
                sender_name = match['sender_display_name']
                if sender_name not in sender_stats:
                    sender_stats[sender_name] = 0
                sender_stats[sender_name] += 1
        
        session_stats_list = sorted(session_stats.values(), key=lambda x: x['count'], reverse=True)
        sender_stats_list = sorted(sender_stats.items(), key=lambda x: x[1], reverse=True)
        sender_stats_list = [{'name': name, 'count': count} for name, count in sender_stats_list]
        
        type_stats_list = [{'type': t, 'count': c} for t, c in sorted(type_stats.items(), key=lambda x: x[1], reverse=True)]
        return {
            "total": total_results,
            "results": paginated_results,
            "limit": limit,
            "offset": offset,
            "session_stats": session_stats_list,
            "sender_stats": sender_stats_list,
            "type_stats": type_stats_list
        }

    def get_message_context(self, message_id: int, context_lines: int = 3, filters: Optional[List[str]] = None) -> Dict:
        import re
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT m1.create_time, m1.session_id
            FROM messages m1
            WHERE m1.id = ?
        """, (message_id,))
        row = cursor.fetchone()
        if not row:
            return {"before": [], "after": []}
        
        create_time = row["create_time"]
        session_id = row["session_id"]
        
        cursor.execute("""
            SELECT id, content, sender_display_name, formatted_time, is_send
            FROM messages
            WHERE session_id = ? AND create_time < ?
            ORDER BY create_time DESC
            LIMIT ?
        """, (session_id, create_time, context_lines))
        before_messages = [dict(row) for row in cursor.fetchall()][::-1]
        
        cursor.execute("""
            SELECT id, content, sender_display_name, formatted_time, is_send
            FROM messages
            WHERE session_id = ? AND create_time > ?
            ORDER BY create_time ASC
            LIMIT ?
        """, (session_id, create_time, context_lines))
        after_messages = [dict(row) for row in cursor.fetchall()]
        
        if filters:
            filtered_before = []
            for msg in before_messages:
                should_filter = False
                for filter_pattern in filters:
                    try:
                        if re.search(filter_pattern, msg['content']):
                            should_filter = True
                            break
                    except re.error:
                        if filter_pattern in msg['content']:
                            should_filter = True
                            break
                if not should_filter:
                    filtered_before.append(msg)
            
            filtered_after = []
            for msg in after_messages:
                should_filter = False
                for filter_pattern in filters:
                    try:
                        if re.search(filter_pattern, msg['content']):
                            should_filter = True
                            break
                    except re.error:
                        if filter_pattern in msg['content']:
                            should_filter = True
                            break
                if not should_filter:
                    filtered_after.append(msg)
            
            before_messages = filtered_before
            after_messages = filtered_after
        
        return {"before": before_messages, "after": after_messages}

    def get_session_messages(self, session_id: int, limit: int = 100, offset: int = 0, filters: Optional[List[str]] = None, sort_order: str = "asc", start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict]:
        import re
        cursor = self.conn.cursor()
        
        base_query = """
            SELECT id, content, sender_display_name, formatted_time, is_send, type, create_time
            FROM messages
            WHERE session_id = ?
        """
        params = [session_id]
        
        if start_time:
            base_query += " AND create_time >= ?"
            params.append(start_time)
        if end_time:
            base_query += " AND create_time <= ?"
            params.append(end_time)
        
        order_by = " ORDER BY create_time "
        if sort_order.lower() == "desc":
            order_by += " DESC"
        else:
            order_by += " ASC"
        
        if limit > 0:
            query = base_query + order_by + " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)
        else:
            query = base_query + order_by
            cursor.execute(query, params)
        
        messages = [dict(row) for row in cursor.fetchall()]
        
        final_filters = filters if filters is not None else []
        if not final_filters:
            return messages
        
        filtered_messages = []
        for msg in messages:
            match = False
            for filter_pattern in final_filters:
                try:
                    if re.search(filter_pattern, msg['content']):
                        match = True
                        break
                except re.error:
                    if filter_pattern in msg['content']:
                        match = True
                        break
            if not match:
                filtered_messages.append(msg)
        
        return filtered_messages

    def get_session_info(self, session_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_sessions(self, session_type: Optional[str] = None) -> List[Dict]:
        cursor = self.conn.cursor()
        if session_type:
            cursor.execute("""
                SELECT id, display_name, type, message_count, last_timestamp
                FROM sessions
                WHERE type = ?
                ORDER BY last_timestamp DESC
            """, (session_type,))
        else:
            cursor.execute("""
                SELECT id, display_name, type, message_count, last_timestamp
                FROM sessions
                ORDER BY last_timestamp DESC
            """)
        sessions = [dict(row) for row in cursor.fetchall()]
        return sessions

    def get_message_position(self, message_id: int, filters: Optional[List[str]] = None, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Optional[Dict]:
        import re
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT m.id, m.session_id, m.create_time
            FROM messages m
            WHERE m.id = ?
        """, (message_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        session_id = row['session_id']
        create_time = row['create_time']
        
        where_conditions = ["session_id = ?", "create_time < ?"]
        where_params = [session_id, create_time]
        
        if filters:
            for filter_pattern in filters:
                if not filter_pattern.startswith('[') and not filter_pattern.startswith('\\['):
                    where_conditions.append("content NOT LIKE ?")
                    where_params.append(f"%{filter_pattern}%")
        
        if start_time:
            where_conditions.append("create_time >= ?")
            where_params.append(start_time)
        if end_time:
            where_conditions.append("create_time <= ?")
            where_params.append(end_time)
        
        where_clause = " AND ".join(where_conditions)
        cursor.execute(f"""
            SELECT COUNT(*) as position
            FROM messages
            WHERE {where_clause}
        """, where_params)
        
        position_result = cursor.fetchone()
        return {
            'id': message_id,
            'session_id': session_id,
            'create_time': create_time,
            'position': position_result['position']
        }

    def import_markdown_file(self, md_path: str, wxid_override: Optional[str] = None) -> bool:
        import re
        from pathlib import Path
        path = Path(md_path)
        if not path.exists():
            return False
            
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Parse session metadata
        display_name = path.stem.replace('_raw', '').replace('.standard', '')
        session_type = "群聊"
        message_count = 0
        wxid = wxid_override if wxid_override else path.stem
        
        for line in lines[:20]:
            line_str = line.strip()
            if line_str.startswith("# 聊天记录:"):
                display_name = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("**类型:**"):
                session_type = line_str.replace("**类型:**", "").strip()
            elif line_str.startswith("**消息数量:**"):
                try:
                    message_count = int(line_str.replace("**消息数量:**", "").strip())
                except:
                    pass

        # If it's a WeChat Official Account, force type to "公众号"
        if wxid.startswith('gh_') or (session_type == "私聊" and wxid.startswith('gh_')):
            session_type = "公众号"

        session_data = {
            "wxid": wxid,
            "nickname": display_name,
            "remark": "",
            "displayName": display_name,
            "type": session_type,
            "lastTimestamp": int(datetime.now().timestamp()),
            "messageCount": message_count
        }
        
        session_id = self.insert_session(session_data, path.name)
        
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
                sender_raw = match.group(2).strip()
                content = match.group(3)
                
                sender_username = sender_raw
                sender_display_name = sender_raw
                if '<' in sender_raw and sender_raw.endswith('>'):
                    parts = sender_raw.split('<', 1)
                    sender_display_name = parts[0].strip()
                    sender_username = parts[1][:-1].strip()
                
                try:
                    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    timestamp = int(dt.timestamp())
                except Exception:
                    timestamp = int(datetime.now().timestamp())
                
                current_msg = {
                    "localId": len(messages) + 1,
                    "createTime": timestamp,
                    "formattedTime": time_str,
                    "type": "text",
                    "localType": 1,
                    "content": content,
                    "isSend": 0,
                    "senderUsername": sender_username,
                    "senderDisplayName": sender_display_name,
                    "source": ""
                }
            else:
                if current_msg and not line_str.startswith('#') and not line_str.startswith('**') and not line_str.startswith('---'):
                    current_msg["content"] += "\n" + line_str
        
        if current_msg:
            messages.append(current_msg)
            
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            if messages:
                t_min = min(msg["createTime"] for msg in messages)
                # Clear old messages since T_min to prevent duplication on incremental import
                cursor.execute("DELETE FROM messages WHERE session_id = ? AND create_time >= ?", (session_id, t_min))
            
            unique_senders = set(msg["senderDisplayName"] for msg in messages)
            for sender in unique_senders:
                cursor.execute("""
                    INSERT OR REPLACE INTO users (username, display_name)
                    VALUES (?, ?)
                """, (sender, sender))
                
            for msg in messages:
                cursor.execute("""
                    INSERT INTO messages 
                    (session_id, local_id, create_time, formatted_time, type, local_type, 
                     content, is_send, sender_username, sender_display_name, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    msg["localId"],
                    msg["createTime"],
                    msg["formattedTime"],
                    msg["type"],
                    msg["localType"],
                    msg["content"],
                    msg["isSend"],
                    msg["senderUsername"],
                    msg["senderDisplayName"],
                    msg["source"]
                ))
            
            if messages:
                # Query database to get correct total count and last message timestamp
                cursor.execute("SELECT COUNT(*) as cnt, MAX(create_time) as max_ts FROM messages WHERE session_id = ?", (session_id,))
                stats = cursor.fetchone()
                total_cnt = stats['cnt'] if stats else len(messages)
                last_ts = stats['max_ts'] if stats and stats['max_ts'] else max(msg["createTime"] for msg in messages)
                
                cursor.execute("""
                    UPDATE sessions 
                    SET message_count = ?, last_timestamp = ?
                    WHERE id = ?
                """, (total_cnt, last_ts, session_id))
                
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            raise e

    def insert_group_member(self, member: Dict) -> int:
        cursor = self.conn.cursor()
        group_name = member.get("group_name")
        wxid = member.get("wxid")
        
        # Try to find corresponding session_id by matching group_name with sessions.display_name
        cursor.execute("SELECT id FROM sessions WHERE display_name = ?", (group_name,))
        session_row = cursor.fetchone()
        session_id = session_row["id"] if session_row else None
        
        cursor.execute("SELECT id FROM group_members WHERE group_name = ? AND wxid = ?", (group_name, wxid))
        row = cursor.fetchone()
        if row:
            member_id = row['id']
            cursor.execute("""
                UPDATE group_members SET 
                    session_id = ?, wechat_name = ?, nickname = ?, 
                    join_time = ?, inviter = ?, message_count = ?
                WHERE id = ?
            """, (
                session_id,
                member.get("wechat_name"),
                member.get("nickname"),
                member.get("join_time"),
                member.get("inviter"),
                member.get("message_count", 0),
                member_id
            ))
        else:
            cursor.execute("""
                INSERT INTO group_members (session_id, group_name, wxid, wechat_name, nickname, join_time, inviter, message_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                group_name,
                wxid,
                member.get("wechat_name"),
                member.get("nickname"),
                member.get("join_time"),
                member.get("inviter"),
                member.get("message_count", 0)
            ))
            member_id = cursor.lastrowid
        self.conn.commit()
        return member_id

    def import_group_members_log(self, log_file_path: str) -> int:
        """解析处理日志.txt文件，将所有群成员导入数据库"""
        import re
        if not Path(log_file_path).exists():
            raise FileNotFoundError(f"日志文件不存在: {log_file_path}")
            
        current_group = None
        in_member_list = False
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            group_match = re.match(r'群名称:\s*(.+)', line)
            if group_match:
                current_group = group_match.group(1).strip()
                in_member_list = False
                continue
                
            processing_match = re.search(r'正在处理:\s*(.+?)(?:_|\.json)', line)
            if processing_match and not current_group:
                current_group = processing_match.group(1).strip()
                continue
                
            if '序号' in line and '微信ID' in line and '微信名' in line:
                in_member_list = True
                continue
                
            if in_member_list and line.startswith('=' * 80):
                in_member_list = False
                continue
                
            if in_member_list and current_group:
                # 解析单行
                pattern = r'^\s*\d+\s+(\S+)\s+(\S+)\s+(.+?)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}|\S+)\s+(\S+)\s+(\d+)\s*$'
                match = re.match(pattern, line)
                if match:
                    member_data = {
                        'group_name': current_group,
                        'wxid': match.group(1),
                        'wechat_name': match.group(2),
                        'nickname': match.group(3).strip(),
                        'join_time': match.group(4),
                        'inviter': match.group(5),
                        'message_count': int(match.group(6))
                    }
                    self.insert_group_member(member_data)
                    count += 1
        return count

    def import_group_members_via_cli(self) -> int:
        """调用 wechat-cli members 命令获取所有群聊的成员并导入数据库"""
        import subprocess
        import json
        import os
        
        # 1. 获取数据库中所有的群聊会话
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, display_name, wxid FROM sessions WHERE type = '群聊'")
        group_sessions = cursor.fetchall()
        
        # 清除原有的 group_members 记录，重新通过 wechat-cli 导入
        cursor.execute("DELETE FROM group_members")
        self.conn.commit()
        
        total_imported = 0
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        
        for sess in group_sessions:
            sess_id = sess["id"]
            group_name = sess["display_name"]
            
            # 调用 wechat-cli members 获取该群的成员列表
            try:
                result = subprocess.run(
                    ['wechat-cli', 'members', '--format', 'json', '--', group_name],
                    capture_output=True, text=True, encoding='utf-8', env=env
                )
                if result.returncode != 0:
                    continue
                
                data = json.loads(result.stdout)
                members = data.get('members', [])
                
                # 统计每个成员在该群聊中的消息数量（因为 messages 中的 sender_username 与 sender_display_name 实际存储的都是显示名/昵称，故需按显示名统计后由昵称映射回微信ID）
                cursor.execute("""
                    SELECT sender_display_name, COUNT(*) as msg_cnt 
                    FROM messages 
                    WHERE session_id = ? 
                    GROUP BY sender_display_name
                """, (sess_id,))
                msg_counts = {row["sender_display_name"]: row["msg_cnt"] for row in cursor.fetchall()}
                
                # 写入 group_members
                for m in members:
                    wxid = m['username']
                    wechat_name = m['nick_name'] or ''
                    nickname = m['display_name'] or wechat_name
                    
                    # 匹配消息数：将可能在 messages 表中出现的显示名/昵称/微信ID的值进行累计
                    possible_names = {wechat_name, nickname, wxid}
                    message_count = 0
                    seen_names = set()
                    for name in possible_names:
                        if name and name not in seen_names:
                            message_count += msg_counts.get(name, 0)
                            seen_names.add(name)
                    
                    cursor.execute("""
                        INSERT INTO group_members (
                            session_id, group_name, wxid, wechat_name, nickname, join_time, inviter, message_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sess_id,
                        group_name,
                        wxid,
                        wechat_name,
                        nickname,
                        '-',
                        '-',
                        message_count
                    ))
                    total_imported += 1
                
                self.conn.commit()
                
            except Exception as e:
                pass
                
        return total_imported

    def get_group_member_overlap(self, session_id: int, exclude_wxids: List[str] = None) -> Dict:
        cursor = self.conn.cursor()
        if exclude_wxids is None:
            exclude_wxids = []
            
        # Get target group info
        cursor.execute("SELECT display_name FROM sessions WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()
        if not session_row:
            return {"error": "会话不存在"}
        target_group = session_row["display_name"]
        
        # Get target group members
        cursor.execute("""
            SELECT wxid, wechat_name, nickname, join_time, inviter, message_count 
            FROM group_members 
            WHERE session_id = ? OR group_name = ?
        """, (session_id, target_group))
        members = [dict(row) for row in cursor.fetchall()]
        
        if not members:
            return {"error": "未找到该群的成员数据，请先导入处理日志"}
            
        total_members = len(members)
        
        # Filter excluded wxids
        members_filtered = [m for m in members if m["wxid"] not in exclude_wxids]
        wxids = [m["wxid"] for m in members_filtered]
        
        # Find all groups these members are in
        all_membership = {}
        chunk_size = 900
        for i in range(0, len(wxids), chunk_size):
            chunk = wxids[i:i+chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"""
                SELECT wxid, group_name 
                FROM group_members 
                WHERE wxid IN ({placeholders})
            """, chunk)
            for row in cursor.fetchall():
                wxid = row["wxid"]
                gname = row["group_name"]
                if wxid not in all_membership:
                    all_membership[wxid] = set()
                all_membership[wxid].add(gname)
                
        # Calculate overlap
        members_in_other_groups = []
        members_only_in_target = []
        group_overlap_counts = {}
        
        for m in members_filtered:
            wxid = m["wxid"]
            member_groups = all_membership.get(wxid, set())
            other_groups = [g for g in member_groups if g != target_group]
            
            if other_groups:
                members_in_other_groups.append({
                    "wxid": wxid,
                    "wechat_name": m["wechat_name"],
                    "nickname": m["nickname"],
                    "join_time": m["join_time"],
                    "inviter": m["inviter"],
                    "message_count": m["message_count"],
                    "groups": other_groups,
                    "group_count": len(other_groups)
                })
                for g in other_groups:
                    group_overlap_counts[g] = group_overlap_counts.get(g, 0) + 1
            else:
                members_only_in_target.append({
                    "wechat_name": m["wechat_name"],
                    "nickname": m["nickname"]
                })
                
        # Sort group distribution
        group_distribution = []
        for gname, count in group_overlap_counts.items():
            pct = count / total_members * 100 if total_members > 0 else 0
            group_distribution.append({
                "name": gname,
                "count": count,
                "percentage": pct
            })
        group_distribution.sort(key=lambda x: x["count"], reverse=True)
        
        # Sort members by group count descending
        members_in_other_groups.sort(key=lambda x: x["group_count"], reverse=True)
        
        return {
            "success": True,
            "target_group": target_group,
            "total_members": total_members,
            "members_in_other_groups": len(members_in_other_groups),
            "members_only_in_target": len(members_only_in_target),
            "group_distribution": group_distribution,
            "members": members_in_other_groups,
            "only_target_members": members_only_in_target
        }

    def get_member_profile(self, wxid: str) -> Dict:
        cursor = self.conn.cursor()
        
        # Get all groups this member belongs to
        cursor.execute("""
            SELECT session_id, group_name, nickname, join_time, inviter, message_count 
            FROM group_members 
            WHERE wxid = ?
            ORDER BY message_count DESC
        """, (wxid,))
        group_rows = cursor.fetchall()
        
        if not group_rows:
            return {"error": f"未找到微信ID: {wxid} 的群成员数据"}
            
        groups = [dict(row) for row in group_rows]
        
        # Extract basic info
        cursor.execute("SELECT wechat_name, nickname FROM group_members WHERE wxid = ? LIMIT 1", (wxid,))
        basic_row = cursor.fetchone()
        wechat_name = basic_row["wechat_name"] if basic_row else ""
        nickname = basic_row["nickname"] if basic_row else ""
        
        total_messages = sum(g["message_count"] for g in groups)
        join_times = [g["join_time"] for g in groups if g["join_time"] and g["join_time"] != '-']
        inviter_info = {g["group_name"]: g["inviter"] for g in groups if g["inviter"] and g["inviter"] != '-'}
        
        # Get co-occurring members (related members)
        group_names = [g["group_name"] for g in groups]
        related_members_info = []
        
        if group_names:
            placeholders = ",".join(["?"] * len(group_names))
            cursor.execute(f"""
                SELECT wxid, wechat_name, nickname, message_count, group_name
                FROM group_members 
                WHERE group_name IN ({placeholders}) AND wxid != ?
            """, group_names + [wxid])
            
            related_data = {}
            for row in cursor.fetchall():
                other_wxid = row["wxid"]
                other_wechat_name = row["wechat_name"]
                other_nickname = row["nickname"]
                other_msg_count = row["message_count"]
                
                if other_wxid not in related_data:
                    related_data[other_wxid] = {
                        "wxid": other_wxid,
                        "wechat_name": other_wechat_name,
                        "nickname": other_nickname,
                        "common_groups_count": 0,
                        "total_messages": 0
                    }
                related_data[other_wxid]["common_groups_count"] += 1
                related_data[other_wxid]["total_messages"] += other_msg_count
                
            related_members_info = sorted(related_data.values(), key=lambda x: (-x["common_groups_count"], -x["total_messages"]))[:50]
            
        group_member_counts = {}
        if group_names:
            placeholders = ",".join(["?"] * len(group_names))
            cursor.execute(f"""
                SELECT group_name, COUNT(*) as count 
                FROM group_members 
                WHERE group_name IN ({placeholders})
                GROUP BY group_name
            """, group_names)
            for row in cursor.fetchall():
                group_member_counts[row["group_name"]] = row["count"]
                
        return {
            "wxid": wxid,
            "wechat_name": wechat_name,
            "nickname": nickname,
            "total_messages": total_messages,
            "group_count": len(groups),
            "groups": groups,
            "join_times": join_times,
            "inviter_info": inviter_info,
            "related_members": related_members_info,
            "group_member_counts": group_member_counts
        }

    def search_group_members(self, keyword: str) -> List[Dict]:
        cursor = self.conn.cursor()
        keyword_pattern = f"%{keyword}%"
        cursor.execute("""
            SELECT wxid, wechat_name, nickname, SUM(message_count) as total_messages, COUNT(group_name) as group_count, GROUP_CONCAT(group_name) as groups
            FROM group_members
            WHERE wxid LIKE ? OR wechat_name LIKE ? OR nickname LIKE ?
            GROUP BY wxid, wechat_name, nickname
            ORDER BY total_messages DESC
            LIMIT 100
        """, (keyword_pattern, keyword_pattern, keyword_pattern))
        
        results = []
        for row in cursor.fetchall():
            groups_str = row["groups"] or ""
            groups_list = [g.strip() for g in groups_str.split(",") if g.strip()]
            results.append({
                "wxid": row["wxid"],
                "wechat_name": row["wechat_name"],
                "nickname": row["nickname"],
                "total_messages": row["total_messages"],
                "group_count": row["group_count"],
                "groups": list(set(groups_list))  # Deduplicate group names
            })
        return results

    def close(self):
        if self.conn:
            self.conn.close()


wechat_db = WechatDatabaseManager()
