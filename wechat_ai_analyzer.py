import hashlib
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from wechat_db import wechat_db

logger = logging.getLogger(__name__)

class WechatAIAnalyzer:
    def __init__(self):
        self.summarizer = None
        self.cache = {}
        self.cache_ttl = 3600  # 缓存 1 小时

    def set_summarizer(self, summarizer):
        self.summarizer = summarizer

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data["timestamp"] < self.cache_ttl:
                return cached_data["data"]
            else:
                del self.cache[cache_key]
        return None

    def _save_to_cache(self, cache_key: str, data: Dict):
        self.cache[cache_key] = {
            "data": data,
            "timestamp": time.time()
        }
        # 清理过期缓存
        current_time = time.time()
        expired_keys = [k for k, v in self.cache.items() if current_time - v["timestamp"] >= self.cache_ttl]
        for k in expired_keys:
            del self.cache[k]

    def _generate_cache_key(self, analysis_type: str, identifier: str, start_time: Optional[int], end_time: Optional[int]) -> str:
        key_data = f"{analysis_type}:{identifier}:{start_time}:{end_time}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _format_messages(self, messages: List[Dict], limit: int = 150) -> str:
        formatted = []
        # If there are more messages than the limit, take the latest ones (end of the list)
        target_messages = messages[-limit:] if len(messages) > limit else messages
        for msg in target_messages:
            formatted.append(
                f"[{msg.get('formatted_time', '')}] {msg.get('sender_display_name', '未知')}: {msg.get('content', '')}"
            )
        return "\n".join(formatted)

    def _call_model(self, system_prompt: str, user_prompt: str) -> str:
        if not self.summarizer:
            return "❌ 本地大模型未加载，无法执行分析"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        try:
            return self.summarizer.chat(messages)
        except Exception as e:
            logger.error(f"AI 分析大模型调用失败: {e}")
            return f"❌ AI 分析大模型调用失败: {str(e)}"

    def analyze_session(self, session_id: int, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            session_info = wechat_db.get_session_info(session_id)
            if not session_info:
                return {"success": False, "error": "会话不存在"}
            
            cache_key = self._generate_cache_key("session", str(session_id), start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}
            
            messages = wechat_db.get_session_messages(
                session_id, 
                limit=0, 
                start_time=start_time, 
                end_time=end_time
            )
            
            if not messages:
                return {"success": False, "error": "该时间段内无聊天记录"}

            # 发言人频次统计作为前缀
            user_stats = {}
            for msg in messages:
                sender = msg.get("sender_display_name", "未知")
                user_stats[sender] = user_stats.get(sender, 0) + 1
            sorted_users = sorted(user_stats.items(), key=lambda x: x[1], reverse=True)
            stats_text = "\n".join([f"- {name}: {count}条消息" for name, count in sorted_users[:15]])

            system_prompt = """你是一个专业的聊天记录分析助手。你的任务是分析群聊记录，提供深入的洞察和分析。
请从以下维度进行分析：
1. 活跃度分析：整体参与度、活跃时间段
2. 主题分析：讨论的主要话题、关键词提取
3. 焦点辩论与冲突检测：若存在不同观点、争议或热烈讨论，提炼出争议主题与核心论据；若无则简要说明
4. 值得关注的信息"""

            user_prompt = f"""请分析以下群聊记录：

群聊名称：{session_info.get('display_name', '未知')}
消息总数：{len(messages)}
发言人活跃排行（前15名）：
{stats_text}

消息记录（前150条）：
{self._format_messages(messages, limit=150)}

请提供详细的分析报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "session_info": {
                    "id": session_info["id"],
                    "name": session_info["display_name"],
                    "type": session_info["type"]
                },
                "statistics": {
                    "total_messages": len(messages),
                    "total_users": len(sorted_users),
                },
                "top_users": [{"name": u[0], "count": u[1]} for u in sorted_users[:10]],
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_user(self, username: str, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            cache_key = self._generate_cache_key("user", username, start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}
            
            search_result = wechat_db.search_by_username(username, limit=0)
            if not search_result.get("results"):
                return {"success": False, "error": "未找到该用户的聊天记录"}
            
            # 汇集该用户所有的消息
            user_messages = []
            for item in search_result["results"]:
                session_name = item["session"]["display_name"]
                for msg in item["messages"]:
                    msg["session_name"] = session_name
                    # 过滤时间段
                    if start_time and msg.get("create_time", 0) < start_time:
                        continue
                    if end_time and msg.get("create_time", 0) > end_time:
                        continue
                    user_messages.append(msg)
            
            if not user_messages:
                return {"success": False, "error": "该时间段内此用户无发言记录"}

            # 计算跨群统计
            session_stats = {}
            for msg in user_messages:
                sname = msg.get("session_name", "未知会话")
                session_stats[sname] = session_stats.get(sname, 0) + 1
            sorted_sessions = sorted(session_stats.items(), key=lambda x: x[1], reverse=True)
            stats_text = "\n".join([f"- {name}: {count}条发言" for name, count in sorted_sessions])

            system_prompt = """你是一个专业的用户行为分析助手。你的任务是分析特定用户的聊天记录，提供深入的用户画像和行为分析。
请从以下维度进行分析：
1. 跨群发言特征：对比用户在不同群中发言的多样性及专注点
2. 角色定位：此人是推广者、答疑专家，还是普通闲聊者？
3. 兴趣偏好：常讨论的话题、关注的核心领域
4. 沟通情感：用词态度、情绪倾向"""

            user_prompt = f"""请分析以下用户的聊天记录：

用户名称：{username}
消息总数：{len(user_messages)}
跨群发言活跃度：
{stats_text}

具体发言记录（前150条）：
{self._format_messages(user_messages, limit=150)}

请提供详细的画像对比分析报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "username": username,
                "statistics": {
                    "total_messages": len(user_messages),
                    "total_sessions": len(sorted_sessions),
                },
                "top_sessions": [{"name": s[0], "count": s[1]} for s in sorted_sessions],
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 自动持久化保存研判结果
            try:
                resolved_wxid = None
                cursor = wechat_db.conn.cursor()
                cursor.execute("""
                    SELECT wxid FROM group_members 
                    WHERE wxid = ? OR wechat_name = ? OR nickname = ? 
                    LIMIT 1
                """, (username, username, username))
                row = cursor.fetchone()
                if row:
                    resolved_wxid = row["wxid"]
                else:
                    cursor.execute("""
                        SELECT sender_username FROM messages 
                        WHERE sender_username = ? OR sender_display_name = ?
                        LIMIT 1
                    """, (username, username))
                    m_row = cursor.fetchone()
                    if m_row:
                        resolved_wxid = m_row["sender_username"]
                
                if resolved_wxid:
                    wechat_db.save_member_personality_analysis(resolved_wxid, "general", ai_analysis)
            except Exception as db_err:
                logger.error(f"保存历史画像研判失败: {db_err}")

            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_user_mbti(self, username: str, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            cache_key = self._generate_cache_key("user_mbti", username, start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}
            
            search_result = wechat_db.search_by_username(username, limit=0)
            if not search_result.get("results"):
                return {"success": False, "error": "未找到该用户的聊天记录"}
            
            # 汇集该用户所有的消息
            user_messages = []
            for item in search_result["results"]:
                session_name = item["session"]["display_name"]
                for msg in item["messages"]:
                    msg["session_name"] = session_name
                    # 过滤时间段
                    if start_time and msg.get("create_time", 0) < start_time:
                        continue
                    if end_time and msg.get("create_time", 0) > end_time:
                        continue
                    user_messages.append(msg)
            
            if not user_messages:
                return {"success": False, "error": "该时间段内此用户无发言记录"}

            # 计算跨群统计
            session_stats = {}
            for msg in user_messages:
                sname = msg.get("session_name", "未知会话")
                session_stats[sname] = session_stats.get(sname, 0) + 1
            sorted_sessions = sorted(session_stats.items(), key=lambda x: x[1], reverse=True)
            stats_text = "\n".join([f"- {name}: {count}条发言" for name, count in sorted_sessions])

            system_prompt = """你是一个充满洞察力、擅长微表情与细节挖掘的性格分析专家与心理咨询师。
你的任务是通过用户的微信聊天记录进行深度细节研判，并推导出其最契合的 MBTI（16种人格）类型。
请根据提供的发言记录（包括语气助词、标点习惯、表达逻辑、讨论焦点、互动姿态等微观细节）进行推理，不要泛泛而谈，而是要专注并结合聊天细节。

请按以下格式生成 Markdown 研判报告：

# 🎭 微信群友性格与 MBTI 研判报告：[用户昵称]

## 🌟 MBTI 人格类型定位
**[推导出的 MBTI 类型，例如：INTJ - 建筑师]**
（用一两句生动、有洞察力的话概括该用户在群聊中的性格底色）

## 🔍 MBTI 四个维度的深度拆解与细节佐证
1. **注意力方向：E（外倾） vs I（内倾）**
   - **倾向判定**：[E 或 I]
   - **聊天细节佐证**：结合其发言频率、是主动发起话题还是被动回应、分享日常多还是专注于特定话题、消息长短、是否频繁互动等细节分析。
2. **信息获取：S（感觉） vs N（直觉）**
   - **倾向判定**：[S 或 N]
   - **聊天细节佐证**：分析其关注的是具体的实操细节、规则条文、真实数据（S倾向），还是宏观趋势、政策逻辑、概念推演、未来可能性（N倾向）。
3. **决策方式：T（思考） vs F（情感）**
   - **倾向判定**：[T 或 F]
   - **聊天细节佐证**：分析其用词是理性、客观、讲逻辑、对事不对人（T倾向），还是温和、有同理心、关注群友感受、喜欢表达情绪共鸣（F倾向）。
4. **生活态度：J（判断） vs P（感知）**
   - **倾向判定**：[J 或 P]
   - **聊天细节佐证**：分析其是否喜欢制定计划、给出明确结论/框架、追求条理与秩序（J倾向），还是随性、开放、保留多种可能性、喜欢随兴闲聊（P倾向）。

## 💬 细节行为与表达风格微观研判
- **语气与用词偏好**：例如常用口头禅、特殊标点（如大量感叹号、省略号、问号）、表情符号（Emoji）的使用习惯。
- **互动姿态与心理防御机制**：在群里遇到意见冲突时的表现（是据理力争、默默潜水、打圆场还是冷嘲热讽），发言中透露出的底层心理诉求（如寻找掌控感、寻求认同、消除焦虑、展示权威等）。

## 🤝 沟通与互动建议
- **触达与说服策略**：如果需要与此人沟通或合作，最有效的表达方式和切入点是什么。
- **潜在盲区与成长建议**：基于其性格特质，指出其在社群交往中可能存在的盲区，并给出温馨的成长建议。
"""

            user_prompt = f"""请分析以下用户的聊天记录，推导其 MBTI 性格类型并进行细节研判：

用户名称：{username}
消息总数：{len(user_messages)}
跨群发言活跃度：
{stats_text}

具体发言记录（前150条）：
{self._format_messages(user_messages, limit=150)}

请提供详细的性格与 MBTI 研判报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "username": username,
                "statistics": {
                    "total_messages": len(user_messages),
                    "total_sessions": len(sorted_sessions),
                },
                "top_sessions": [{"name": s[0], "count": s[1]} for s in sorted_sessions],
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 自动持久化保存研判结果
            try:
                resolved_wxid = None
                cursor = wechat_db.conn.cursor()
                cursor.execute("""
                    SELECT wxid FROM group_members 
                    WHERE wxid = ? OR wechat_name = ? OR nickname = ? 
                    LIMIT 1
                """, (username, username, username))
                row = cursor.fetchone()
                if row:
                    resolved_wxid = row["wxid"]
                else:
                    cursor.execute("""
                        SELECT sender_username FROM messages 
                        WHERE sender_username = ? OR sender_display_name = ?
                        LIMIT 1
                    """, (username, username))
                    m_row = cursor.fetchone()
                    if m_row:
                        resolved_wxid = m_row["sender_username"]
                
                if resolved_wxid:
                    wechat_db.save_member_personality_analysis(resolved_wxid, "mbti", ai_analysis)
            except Exception as db_err:
                logger.error(f"保存历史性格研判失败: {db_err}")

            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_group_theme(self, group_name: str, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            # 找到 session
            cursor = wechat_db.conn.cursor()
            cursor.execute("SELECT id FROM sessions WHERE display_name = ?", (group_name,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": f"未找到群聊：{group_name}"}
            session_id = row["id"]

            cache_key = self._generate_cache_key("group_theme", group_name, start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}

            messages = wechat_db.get_session_messages(
                session_id, limit=0, start_time=start_time, end_time=end_time
            )
            if not messages:
                return {"success": False, "error": "该时间段内群里无消息"}

            system_prompt = """你是一个专业的群聊主题分析助手。你的任务是分析特定群聊在某个时间段的聊天主题，提供详细的主题分析报告。
请从以下维度进行分析：
1. 主题识别：识别主要讨论主题，并用关键词或短语概括
2. 主题热度：讨论热度（消息数、热烈程度）
3. 讨论脉络与关键结论：群友得出了什么重要结论或分享了什么干货"""

            user_prompt = f"""请分析以下群聊记录的讨论主题：

群聊名称：{group_name}
总消息数：{len(messages)}

具体消息记录（前150条）：
{self._format_messages(messages, limit=150)}

请生成主题分析报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "group_name": group_name,
                "total_messages": len(messages),
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_user_relations(self, username: str, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            cache_key = self._generate_cache_key("user_relations", username, start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}

            search_result = wechat_db.search_by_username(username, limit=0)
            if not search_result.get("results"):
                return {"success": False, "error": "未找到该用户的发言记录"}

            # 收集该用户所有相关的消息及会话消息
            all_relevant_msgs = []
            for item in search_result["results"]:
                session_id = item["session"]["id"]
                messages = wechat_db.get_session_messages(
                    session_id, limit=0, start_time=start_time, end_time=end_time
                )
                all_relevant_msgs.extend(messages)
            
            if not all_relevant_msgs:
                return {"success": False, "error": "该时间段内无相关互动记录"}

            # 简易计算关系频次
            # 统计谁提到了该用户，或者该用户和谁互动最为频繁（在同一会话中先后发言）
            interactions = {}
            for i, msg in enumerate(all_relevant_msgs):
                sender = msg.get("sender_display_name", "")
                if sender == username:
                    # 获取前两条和后两条消息的发送者作为可能互动人
                    indices = [i-2, i-1, i+1, i+2]
                    for idx in indices:
                        if 0 <= idx < len(all_relevant_msgs):
                            other = all_relevant_msgs[idx].get("sender_display_name", "")
                            if other and other != username:
                                interactions[other] = interactions.get(other, 0) + 1
            
            sorted_interactions = sorted(interactions.items(), key=lambda x: x[1], reverse=True)
            stats_text = "\n".join([f"- {name}: 临近发言互动 {count} 次" for name, count in sorted_interactions[:15]])

            # 用 Mermaid 语法表示网络图谱
            mermaid_nodes = [f'    center["👤 {username}"]']
            for name, count in sorted_interactions[:8]:
                mermaid_nodes.append(f'    center ===|互动 {count}次| {name}["👤 {name}"]')
            mermaid_chart = "graph TD\n" + "\n".join(mermaid_nodes)

            system_prompt = """你是一个专业的用户关系网络分析助手。你的任务是分析特定用户与其他用户的关系网络，提供详细的关系分析报告。
请基于互动频率数据和消息内容：
1. 评估该用户与其他用户的亲密度和交流特点
2. 总结其主要互动圈层和关注方向
3. 给出网络互动关系结论"""

            user_prompt = f"""请分析用户 '{username}' 与其他群友的关系网络：

用户名称：{username}
预统计互动频度：
{stats_text}

Mermaid 关系网草图：
```mermaid
{mermaid_chart}
```

请给出详细的关系报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "username": username,
                "mermaid_chart": mermaid_chart,
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_top5(self, session_id: int, start_time: Optional[int] = None, end_time: Optional[int] = None, use_cache: bool = True) -> Dict:
        try:
            session_info = wechat_db.get_session_info(session_id)
            if not session_info:
                return {"success": False, "error": "会话不存在"}
            
            cache_key = self._generate_cache_key("top5", str(session_id), start_time, end_time)
            if use_cache:
                cached = self._get_from_cache(cache_key)
                if cached:
                    return {"success": True, "data": cached, "from_cache": True}
            
            cursor = wechat_db.conn.cursor()
            
            # Find the top 5 senders in this session by message count
            query_stats = """
                SELECT sender_display_name, sender_username, COUNT(*) as count
                FROM messages
                WHERE session_id = ? AND sender_display_name IS NOT NULL AND sender_display_name != ''
            """
            params_stats = [session_id]
            if start_time:
                query_stats += " AND create_time >= ?"
                params_stats.append(start_time)
            if end_time:
                query_stats += " AND create_time <= ?"
                params_stats.append(end_time)
                
            query_stats += " GROUP BY sender_display_name, sender_username ORDER BY count DESC LIMIT 5"
            cursor.execute(query_stats, params_stats)
            top5_rows = cursor.fetchall()
            
            if not top5_rows:
                return {"success": False, "error": "该时间段内无活跃发言人数据"}
                
            # For each of the top 5 senders, fetch up to 40 messages they sent in this session
            top5_data = []
            for row in top5_rows:
                sender_name = row["sender_display_name"]
                sender_user = row["sender_username"]
                msg_count = row["count"]
                
                query_msgs = """
                    SELECT content, formatted_time, create_time
                    FROM messages
                    WHERE session_id = ? AND sender_display_name = ?
                """
                params_msgs = [session_id, sender_name]
                if start_time:
                    query_msgs += " AND create_time >= ?"
                    params_msgs.append(start_time)
                if end_time:
                    query_msgs += " AND create_time <= ?"
                    params_msgs.append(end_time)
                
                query_msgs += " ORDER BY create_time DESC LIMIT 40"
                cursor.execute(query_msgs, params_msgs)
                msgs = [dict(r) for r in cursor.fetchall()]
                msgs.reverse()
                
                top5_data.append({
                    "name": sender_name,
                    "username": sender_user,
                    "count": msg_count,
                    "messages": msgs
                })
                
            query_total = "SELECT COUNT(*) as total FROM messages WHERE session_id = ?"
            params_total = [session_id]
            if start_time:
                query_total += " AND create_time >= ?"
                params_total.append(start_time)
            if end_time:
                query_total += " AND create_time <= ?"
                params_total.append(end_time)
            cursor.execute(query_total, params_total)
            total_session_msgs = cursor.fetchone()["total"]

            top5_summary_lines = []
            detailed_msgs_block = []
            for idx, user_info in enumerate(top5_data):
                pct = (user_info["count"] / total_session_msgs * 100) if total_session_msgs > 0 else 0
                top5_summary_lines.append(f"{idx+1}. {user_info['name']} (账号/ID: {user_info['username'] or '未知'}): 发言 {user_info['count']} 条，占该时间段群发言总数 ({total_session_msgs}条) 的 {pct:.2f}%")
                
                formatted_msgs = []
                for m in user_info["messages"]:
                    formatted_msgs.append(f"[{m.get('formatted_time', '')}] {m.get('content', '')}")
                msgs_str = "\n".join(formatted_msgs)
                
                detailed_msgs_block.append(f"发言人 {idx+1}: {user_info['name']}\n近期发言样本：\n{msgs_str}\n" + "-"*40)
                
            summary_text = "\n".join(top5_summary_lines)
            detailed_text = "\n\n".join(detailed_msgs_block)
            
            system_prompt = """你是一个群聊社交网络与行为研判专家。你的任务是分析群聊中最活跃的前五名成员，生成一份深度对比研判报告。
请从以下维度进行综合性分析并生成 Markdown 报告：
1. 【群内活跃度与影响力概览】：分析前五名活跃成员的发言占比、活跃规律等。
2. 【用户画像与群内角色研判】：对每一位活跃成员进行画像（分析其关注主题、言论态度、在群聊中扮演的角色，例如：是话题发起者、技术输出/答疑者、信息转发者、闲聊活跃气氛者还是情绪宣泄者）。
3. 【社交互动与人际关系透视】：这五个人之间是否存在互动、是否存在观点抱团或交锋，以及他们是如何共同主导/影响群聊舆论和氛围的。
4. 【总结与研判建议】：针对这几位核心活跃分子，总结群聊的舆论核心驱动力，并提供研判建议。
请生成专业、深入、结构清晰的报告。"""

            user_prompt = f"""请分析以下群聊中最活跃的前五名成员的发言特征：
            
群聊名称：{session_info.get('display_name', '未知')}
消息统计时间段内总消息：{total_session_msgs} 条

【活跃前五名基本信息】：
{summary_text}

【前五名成员的发言样本（每人最多40条最新记录）】：
{detailed_text}

请生成详细的活跃前五名对比研判报告。"""

            ai_analysis = self._call_model(system_prompt, user_prompt)
            result = {
                "session_info": {
                    "id": session_info["id"],
                    "name": session_info["display_name"],
                    "type": session_info["type"]
                },
                "statistics": {
                    "total_messages": total_session_msgs,
                },
                "top5_users": [{"name": u["name"], "count": u["count"], "username": u["username"]} for u in top5_data],
                "ai_analysis": ai_analysis,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._save_to_cache(cache_key, result)
            return {"success": True, "data": result, "from_cache": False}
            
        except Exception as e:
            logger.exception("活跃前五研判失败")
            return {"success": False, "error": str(e)}

    def chat_analyze(self, query: str, context: List[Dict], use_cache: bool = True) -> Dict:
        try:
            # 简易识别意图：根据关键字匹配
            # "主题" 或 "讨论" -> analyze_group_theme
            # "关系" 或 "圈子" -> analyze_user_relations
            # "画像" 或 "跨群" -> analyze_user
            # 否则做对话分析
            system_prompt = "你是一个专业的聊天记录分析助手，能够处理用户的各种查询请求。"
            
            # 使用本地模型分析
            ai_result = self._call_model(system_prompt, f"用户提问：{query}\n\n上下文信息：{json.dumps(context, ensure_ascii=False)}")
            
            return {
                "success": True,
                "data": {
                    "query": query,
                    "result": ai_result,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


wechat_ai_analyzer = WechatAIAnalyzer()
