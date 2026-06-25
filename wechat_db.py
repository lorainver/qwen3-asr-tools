import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class WechatDatabaseManager:
    def __init__(self, db_path: str = "D:/qwen3-asr/knowledge_base/wechat_chat_records.db"):
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

        self.conn.commit()

    def insert_session(self, session_data: Dict, file_name: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sessions 
            (wxid, nickname, remark, display_name, type, last_timestamp, message_count, file_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_data.get("wxid"),
            session_data.get("nickname"),
            session_data.get("remark"),
            session_data.get("displayName"),
            session_data.get("type"),
            session_data.get("lastTimestamp"),
            session_data.get("messageCount"),
            file_name
        ))
        self.conn.commit()
        return cursor.lastrowid

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

    def search_by_keyword(self, keyword: str, session_id: Optional[int] = None, sender_display_name: Optional[str] = None, context_lines: int = 3, limit: int = 50, offset: int = 0, filters: Optional[List[str]] = None, sort_by: str = "time", sort_order: str = "desc", start_time: Optional[int] = None, end_time: Optional[int] = None, show_context: bool = False, only_sender: bool = False) -> Dict:
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
                SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
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
                    SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.content LIKE ?
                """
                params = [f"%{keyword}%"]
            else:
                base_query = """
                    SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
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
        
        if sender_display_name:
            base_query += " AND m.sender_display_name LIKE ?"
            params.append(f"%{sender_display_name}%")
        
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
        
        for match in filtered_matches:
            if match['session_id']:
                session_key = f"{match['session_id']}-{match['session_name']}"
                if session_key not in session_stats:
                    session_stats[session_key] = {
                        'id': match['session_id'],
                        'name': match['session_name'],
                        'count': 0
                    }
                session_stats[session_key]['count'] += 1
            
            if match['sender_display_name']:
                sender_name = match['sender_display_name']
                if sender_name not in sender_stats:
                    sender_stats[sender_name] = 0
                sender_stats[sender_name] += 1
        
        session_stats_list = sorted(session_stats.values(), key=lambda x: x['count'], reverse=True)
        sender_stats_list = sorted(sender_stats.items(), key=lambda x: x[1], reverse=True)
        sender_stats_list = [{'name': name, 'count': count} for name, count in sender_stats_list]
        
        return {
            "total": total_results,
            "results": paginated_results,
            "limit": limit,
            "offset": offset,
            "session_stats": session_stats_list,
            "sender_stats": sender_stats_list
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

    def import_markdown_file(self, md_path: str) -> bool:
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
        wxid = path.stem
        
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
                sender = match.group(2)
                content = match.group(3)
                
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
                    "senderUsername": sender,
                    "senderDisplayName": sender,
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
                last_ts = max(msg["createTime"] for msg in messages)
                cursor.execute("""
                    UPDATE sessions 
                    SET message_count = ?, last_timestamp = ?
                    WHERE id = ?
                """, (len(messages), last_ts, session_id))
                
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            raise e

    def close(self):
        if self.conn:
            self.conn.close()


wechat_db = WechatDatabaseManager()
