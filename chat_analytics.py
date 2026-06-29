import sys
import os
import sqlite3
import json
import re
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

# 导入 SQLite 数据库管理实例
from wechat_db import wechat_db

def safe_print(*args, **kwargs):
    msg = " ".join(map(str, args))
    try:
        sys.stdout.write(msg + kwargs.get('end', '\n'))
        sys.stdout.flush()
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'utf-8'
        try:
            sys.stdout.write(msg.encode(enc, errors='replace').decode(enc) + kwargs.get('end', '\n'))
            sys.stdout.flush()
        except Exception:
            try:
                sys.stdout.write(msg.encode('gbk', errors='replace').decode('gbk') + kwargs.get('end', '\n'))
                sys.stdout.flush()
            except Exception:
                sys.stdout.write(msg.encode('ascii', errors='replace').decode('ascii') + kwargs.get('end', '\n'))
                sys.stdout.flush()

print = safe_print


# 保证本地 jieba / networkx 运行
try:
    import jieba
    import jieba.analyse
except ImportError:
    print("[Error] 请先运行: venv\\Scripts\\pip.exe install jieba")
    sys.exit(1)

try:
    import networkx as nx
except ImportError:
    print("[Error] 请先运行: venv\\Scripts\\pip.exe install networkx")
    sys.exit(1)


# 典型学校及机构白名单默认值
DEFAULT_SCHOOL_KEYWORDS = ["育才", "巴蜀", "南开", "一中", "八中", "西大附中", "求精", "辅仁", "川外附中", "青木关"]
DEFAULT_INST_KEYWORDS = ["学而思", "新东方", "高途", "猿辅导", "作业帮", "精锐", "卓越"]

def load_dict_keywords(filename, default_list):
    """从本地文本文件读取关键字，每行一个，忽略以#开头的注释和空行"""
    try:
        path = Path(__file__).parent / filename
        if path.exists():
            words = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        words.append(line)
            if words:
                return words
    except Exception as e:
        sys.stderr.write(f"[Warning] 加载 {filename} 失败: {e}\n")
    return default_list

SCHOOL_KEYWORDS = load_dict_keywords("school_dict.txt", DEFAULT_SCHOOL_KEYWORDS)
INST_KEYWORDS = load_dict_keywords("institution_dict.txt", DEFAULT_INST_KEYWORDS)


class ChatAnalytics:
    def __init__(self, db_path="D:/Work/Useful_Tools/chat_record_analyzer/data/chat_records.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            print(f"[Warning] 数据库文件不存在: {self.db_path}，将创建新库。")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # 加载自定义词典 (如果存在)
        dict_path = Path(__file__).parent / "user_dict.txt"
        if dict_path.exists():
            jieba.load_userdict(str(dict_path))
            print(f"[+] 成功加载行业自定义词表: {dict_path.name}")
        else:
            print("[ℹ️] 未找到 user_dict.txt，使用默认分词字典。")

    @staticmethod
    def static_extract_resources(content):
        """静态函数：提取单条消息文本中的实体和链接"""
        extracted = []
        if not content:
            return extracted
            
        book_pattern = re.compile(r'《([^》]{2,25})》')
        url_pattern = re.compile(r'(https?://[a-zA-Z0-9./?=&_-]+)')
        
        # 1. 提取书籍
        for b in book_pattern.findall(content):
            extracted.append({"type": "book", "value": b})
            
        # 2. 提取链接
        for u in url_pattern.findall(content):
            extracted.append({"type": "url", "value": u})
                
        # 3. 提取学校
        for sch in SCHOOL_KEYWORDS:
            if sch in content:
                extracted.append({"type": "school", "value": sch})
                
        # 4. 提取机构
        for inst in INST_KEYWORDS:
            if inst in content:
                extracted.append({"type": "institution", "value": inst})
                
        return extracted

    def extract_and_save_all(self):
        """全量扫描并提取 messages 中所有的实体和干货链接，写入数据库"""
        print("\n🚀 开始全量扫描本地微信记录并提取干货资源...")
        cursor = self.conn.cursor()
        
        # 统计文本消息数
        cursor.execute("SELECT COUNT(*) FROM messages WHERE type IN ('text', '文本消息')")
        total_text_messages = cursor.fetchone()[0]
        print(f"[*] 共发现 {total_text_messages} 条文本消息需要扫描。")
        
        cursor.execute("SELECT id, session_id, content, sender_display_name, create_time FROM messages WHERE type IN ('text', '文本消息')")
        
        count = 0
        extracted_count = 0
        
        # 使用批量插入以提高速度
        while True:
            rows = cursor.fetchmany(5000)
            if not rows:
                break
            
            # 保存资源，使用 insert or ignore 防重复
            for r in rows:
                content = r['content']
                res_list = self.static_extract_resources(content)
                if res_list:
                    for res in res_list:
                        wechat_db.save_extracted_resource(
                            session_id=r['session_id'],
                            message_id=r['id'],
                            resource_type=res['type'],
                            resource_value=res['value'],
                            raw_content=content,
                            sender_name=r['sender_display_name'],
                            create_time=r['create_time']
                        )
                        extracted_count += 1
                count += 1
                if count % 10000 == 0:
                    print(f"  已扫描 {count}/{total_text_messages} 条消息，提取出 {extracted_count} 个资源...")
                    
        print(f"\n🎉 全量提取完成！共扫描 {count} 条消息，提取出 {extracted_count} 个实体和链接资源存入 SQLite 数据库。")

    def extract_session_resources(self, session_ident):
        """扫描并提取指定会话（ID 或 wxid 等）的所有文本消息中的资源到 SQLite"""
        session = self._resolve_session(session_ident)
        session_id = session['id']
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT id, content, sender_display_name, create_time FROM messages WHERE session_id = ? AND type IN ('text', '文本消息')", (session_id,))
        rows = cursor.fetchall()
        
        extracted_count = 0
        for r in rows:
            content = r['content']
            res_list = self.static_extract_resources(content)
            if res_list:
                for res in res_list:
                    wechat_db.save_extracted_resource(
                        session_id=session_id,
                        message_id=r['id'],
                        resource_type=res['type'],
                        resource_value=res['value'],
                        raw_content=content,
                        sender_name=r['sender_display_name'],
                        create_time=r['create_time']
                    )
                    extracted_count += 1
        return extracted_count

    def _resolve_session(self, session_ident):
        """支持通过 ID (数字) 或 wxid (字符串) 查找会话信息"""
        cursor = self.conn.cursor()
        if str(session_ident).isdigit():
            cursor.execute("SELECT id, wxid, nickname, remark FROM sessions WHERE id = ?", (int(session_ident),))
        else:
            cursor.execute("SELECT id, wxid, nickname, remark FROM sessions WHERE wxid = ? OR nickname = ? OR remark = ?", 
                           (session_ident, session_ident, session_ident))
        row = cursor.fetchone()
        if not row:
            print(f"[Error] 找不到会话: {session_ident}")
            sys.exit(1)
        return dict(row)

    def list_sessions(self):
        """列出所有有效会话"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.id, s.wxid, s.nickname, s.remark, s.message_count 
            FROM sessions s
            ORDER BY s.message_count DESC
        """)
        rows = cursor.fetchall()
        print("\n=== 可分析的微信会话列表 ===")
        print(f"{'ID':<6} | {'会话名称/备注':<30} | {'微信内部ID (wxid)':<35} | {'消息数':<8}")
        print("-" * 90)
        for r in rows:
            name = r['remark'] or r['nickname'] or "未知名称"
            print(f"{r['id']:<6} | {name[:30]:<30} | {r['wxid']:<35} | {r['message_count']:<8}")
        print("-" * 90)

    # ==================== 1. 主题热点与演变分析 ====================
    def analyze_topics(self, session_ident, top_k=15, filter_month=None):
        """分析指定群聊的主题与热词"""
        session = self._resolve_session(session_ident)
        session_id = session['id']
        name = session['remark'] or session['nickname']
        print(f"\n📊 正在分析会话主题: {name} (ID: {session_id})")
        
        cursor = self.conn.cursor()
        query = "SELECT create_time, content FROM messages WHERE session_id = ? AND type IN ('text', '文本消息')"
        params = [session_id]
        if filter_month:
            # 格式 YYYY-MM
            query += " AND strftime('%Y-%m', datetime(create_time, 'unixepoch')) = ?"
            params.append(filter_month)
            
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            print("[-] 该时间段内没有文本消息。")
            return

        print(f"[*] 共获取到 {len(rows)} 条文本消息，正在进行中文分词与权重计算...")
        
        # 按月分组汇总文本
        monthly_text = defaultdict(list)
        all_text = []
        for r in rows:
            content = r['content'] or ''
            # 简单清洗，去除表情符号及系统引用标记
            content = re.sub(r'\[\w+\]', '', content)
            content = re.sub(r'>\s*@.*?\s*\n', '', content)
            
            dt = datetime.fromtimestamp(r['create_time'])
            month_str = dt.strftime("%Y-%m")
            monthly_text[month_str].append(content)
            all_text.append(content)

        # 整体热词分析
        print(f"\n🔍 === 全期 Top {top_k} 核心热词 (TF-IDF) ===")
        combined_all = " ".join(all_text)
        # 仅保留名词 (n)、人名 (nr)、地名 (ns)、机构团体名 (nt)
        tags = jieba.analyse.extract_tags(combined_all, topK=top_k, withWeight=True, allowPOS=('n', 'nr', 'ns', 'nt'))
        print(f"{'热词':<15} | {'TF-IDF 权重 (重要性指数)':<25}")
        print("-" * 45)
        for word, weight in tags:
            print(f"{word:<15} | {weight:.4f}")
        
        # 主题演变分析 (按月份查看趋势)
        if len(monthly_text) > 1 and not filter_month:
            print("\n📈 === 按月份主题演变趋势 ===")
            for month in sorted(monthly_text.keys()):
                month_combined = " ".join(monthly_text[month])
                month_tags = jieba.analyse.extract_tags(month_combined, topK=5, allowPOS=('n', 'nr', 'ns', 'nt'))
                print(f"📅 {month} 月核心热点: {', '.join(month_tags)}")

    # ==================== 2. 社交网络与关联度分析 ====================
    def analyze_network(self, session_ident, export_json_path=None):
        """分析会话的引用/回复社交网络关系"""
        session = self._resolve_session(session_ident)
        session_id = session['id']
        name = session['remark'] or session['nickname']
        print(f"\n🌐 正在构建群聊社交互动网络: {name} (ID: {session_id})")

        cursor = self.conn.cursor()
        # 获取群中所有的回复消息
        cursor.execute("""
            SELECT sender_display_name, content 
            FROM messages 
            WHERE session_id = ? AND content LIKE '> @%'
        """, (session_id,))
        rows = cursor.fetchall()

        if not rows:
            print("[-] 该群聊中没有发现标准的 @ 引用回复结构。")
            return

        # 提取边关系: (回复人, 被回复人)
        reply_pattern = re.compile(r'^>\s*@([^\s：:]+)')
        edges = []
        for r in rows:
            replier = r['sender_display_name']
            content = r['content'] or ''
            match = reply_pattern.match(content)
            if match:
                original_poster = match.group(1)
                # 排除自己回复自己
                if replier and original_poster and replier != original_poster:
                    edges.append((replier, original_poster))

        if not edges:
            print("[-] 未解析出有效的互动边。")
            return

        print(f"[*] 解析出 {len(edges)} 条有效互动回复边，正在计算图指标...")

        # 构建 networkx 有向图
        G = nx.DiGraph()
        for u, v in edges:
            if G.has_edge(u, v):
                G[u][v]['weight'] += 1
            else:
                G.add_edge(u, v, weight=1)

        # 度中心性（谁被回复得最多/谁最活跃）
        in_degree = nx.in_degree_centrality(G)  # 被动互动（影响力）
        out_degree = nx.out_degree_centrality(G) # 主动回复（积极性）
        
        # 中介中心度（谁是连结不同小圈子的核心桥梁）
        betweenness = nx.betweenness_centrality(G)

        # 排行榜
        sorted_influence = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]
        sorted_bridge = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]

        print(f"\n👑 === 群核心影响力排行榜 (被@/被回复最多) ===")
        print(f"{'名次':<5} | {'家长昵称':<20} | {'影响力得分':<15}")
        print("-" * 45)
        for idx, (node, score) in enumerate(sorted_influence, 1):
            print(f"{idx:<5} | {node:<20} | {score:.4f}")

        print(f"\n🌉 === 群社交桥梁/中介排行榜 (圈子协调者) ===")
        print(f"{'名次':<5} | {'家长昵称':<20} | {'中介度得分':<15}")
        print("-" * 45)
        for idx, (node, score) in enumerate(sorted_bridge, 1):
            print(f"{idx:<5} | {node:<20} | {score:.4f}")

        # 导出为 ECharts 兼容的关系图数据
        if export_json_path:
            nodes_data = []
            # 用度来做节点大小
            for node in G.nodes():
                deg = G.degree(node)
                nodes_data.append({
                    "name": node,
                    "symbolSize": max(10, min(deg * 3, 80)),
                    "value": deg
                })
            
            links_data = []
            for u, v, d in G.edges(data=True):
                links_data.append({
                    "source": u,
                    "target": v,
                    "value": d['weight']
                })
                
            export_data = {
                "nodes": nodes_data,
                "links": links_data
            }
            
            with open(export_json_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            print(f"\n[+] 社交网络关系图数据已成功导出至 JSON: {export_json_path}")

    # ==================== 3. 实体与干货资源提取器 ====================
    def extract_resources(self, session_ident, res_type="all"):
        """扫描并提取群内高频出现的书籍、网盘链接、学校、机构等干货资源"""
        session = self._resolve_session(session_ident)
        session_id = session['id']
        name = session['remark'] or session['nickname']
        print(f"\n📦 正在扫描群聊干货与资源: {name} (ID: {session_id})")

        cursor = self.conn.cursor()
        cursor.execute("SELECT sender_display_name, content, create_time FROM messages WHERE session_id = ?", (session_id,))
        rows = cursor.fetchall()

        # 定义匹配规则
        book_pattern = re.compile(r'《([^》]{2,25})》')
        url_pattern = re.compile(r'(https?://[a-zA-Z0-9./?=&_-]+)')
        pan_pattern = re.compile(r'(pan\.baidu\.com/s/[a-zA-Z0-9_-]+|quark\.cn/s/[a-zA-Z0-9_-]+)')
        
        # 典型学校白名单（可根据地区增减）
        school_keywords = ["育才", "巴蜀", "南开", "一中", "八中", "西大附中", "求精", "辅仁", "川外附中", "青木关"]
        # 典型培训机构白名单
        inst_keywords = ["学而思", "新东方", "高途", "猿辅导", "作业帮", "精锐", "卓越"]

        extracted_books = Counter()
        extracted_urls = defaultdict(list)
        extracted_schools = Counter()
        extracted_insts = Counter()

        for r in rows:
            content = r['content'] or ''
            sender = r['sender_display_name'] or "未知"
            
            # 1. 提取书籍
            found_books = book_pattern.findall(content)
            for b in found_books:
                extracted_books[b] += 1
                
            # 2. 提取网盘/链接
            found_urls = url_pattern.findall(content)
            for u in found_urls:
                # 区分网盘链接与普通链接
                if any(p in u for p in ["pan.baidu.com", "quark.cn", "aliyundrive"]):
                    extracted_urls["网盘/云盘资源"].append((u, sender))
                else:
                    extracted_urls["普通链接/公众号文章"].append((u, sender))
                    
            # 3. 提取学校实体
            for sch in school_keywords:
                if sch in content:
                    extracted_schools[sch] += 1
                    
            # 4. 提取机构实体
            for inst in inst_keywords:
                if inst in content:
                    extracted_insts[inst] += 1

        # 结果输出
        if res_type in ["all", "book"] and extracted_books:
            print("\n📚 === 推荐频率最高的书单/教辅排行 ===")
            print(f"{'书名':<30} | {'提及次数':<8}")
            print("-" * 42)
            for book, count in extracted_books.most_common(10):
                print(f"《{book}》{'' if len(book) > 28 else ' '*(28-len(book))} | {count:<8}")

        if res_type in ["all", "school"] and extracted_schools:
            print("\n🏫 === 被高频提及的学校/考点排行榜 ===")
            print(f"{'学校名称':<15} | {'提及次数':<8}")
            print("-" * 28)
            for sch, count in extracted_schools.most_common(10):
                print(f"{sch:<15} | {count:<8}")

        if res_type in ["all", "institution"] and extracted_insts:
            print("\n🏢 === 被高频提及的培训机构/品牌 ===")
            print(f"{'机构名称':<15} | {'提及次数':<8}")
            print("-" * 28)
            for inst, count in extracted_insts.most_common(10):
                print(f"{inst:<15} | {count:<8}")

        if res_type in ["all", "url"] and extracted_urls:
            print("\n🔗 === 局盘/资源链接分享汇总 ===")
            for cat, items in extracted_urls.items():
                print(f"\n【{cat}】(共 {len(items)} 条):")
                # 去重并只显示前 8 条
                seen = set()
                count = 0
                for url, sender in items:
                    if url not in seen:
                        seen.add(url)
                        print(f"  - {url} (分享人: {sender})")
                        count += 1
                        if count >= 8:
                            print("    ... 其余资源已省略 ...")
                            break


def main():
    parser = argparse.ArgumentParser(description="微信聊天记录数据挖掘与分析工具（纯编码驱动版）")
    parser.add_argument('--list', action='store_true', help="列出所有可分析的微信会话及其 ID")
    parser.add_argument('--session', type=str, help="指定要分析的会话 ID 或备注名称")
    parser.add_argument('--topics', action='store_true', help="启用主题热点与时间演变分析")
    parser.add_argument('--network', action='store_true', help="启用回复关系图谱与影响力分析")
    parser.add_argument('--resources', action='store_true', help="启用书籍/链接/实体干货自动提取")
    parser.add_argument('--extract-all', action='store_true', help="从整个消息表中全量扫描并提取所有干货资源到 SQLite 表")
    
    # 辅助过滤与导出参数
    parser.add_argument('--top', type=int, default=15, help="热词提取数量，默认 15")
    parser.add_argument('--month', type=str, help="限制分析的具体月份，格式 YYYY-MM")
    parser.add_argument('--export-json', type=str, help="导出社交网络关系数据到指定 JSON 路径")
    parser.add_argument('--res-type', type=str, default="all", choices=["all", "book", "url", "school", "institution"],
                        help="限制提取的资源类型")

    args = parser.parse_args()
    
    analytics = ChatAnalytics()

    if args.list:
        analytics.list_sessions()
        return

    if args.extract_all:
        analytics.extract_and_save_all()
        return

    if not args.session:
        print("[Error] 请使用 --session 指定要分析的会话（ID 或名称），或使用 --list 查看会话列表，或使用 --extract-all 全量提取资源。")
        sys.exit(1)

    if args.topics:
        analytics.analyze_topics(args.session, top_k=args.top, filter_month=args.month)

    if args.network:
        analytics.analyze_network(args.session, export_json_path=args.export_json)

    if args.resources:
        analytics.extract_resources(args.session, res_type=args.res_type)


if __name__ == '__main__':
    main()
