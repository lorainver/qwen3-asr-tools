"""
实现全量多类型搜索: 搜索全部群聊/私聊/公众号，支持按类型分组展示
"""
import re

# ═══════════════════════════════════════════════════════════
# 1. 修改 wechat_db.py — 增加 session_type 参数和分组统计
# ═══════════════════════════════════════════════════════════
with open('wechat_db.py', 'r', encoding='utf-8') as f:
    db = f.read()

# 1a. 修改函数签名 — 在 only_sender 后添加 session_type 参数
old_sig = "only_sender: bool = False) -> Dict:"
new_sig = "only_sender: bool = False, session_type: Optional[str] = None) -> Dict:"
db = db.replace(old_sig, new_sig, 1)
print('1a. Signature updated')

# 1b. SELECT 增加 s.type 字段
old_select = """SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.content LIKE ?"""
new_select = """SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.content LIKE ?"""
db = db.replace(old_select, new_select, 1)
print('1b. SELECT + session_type (LIKE branch)')

# 1c. SELECT 增加 s.type 字段 — FTS 分支
old_select_fts = """SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.id IN (
                        SELECT rowid FROM messages_fts 
                        WHERE messages_fts MATCH ?
                    )"""
new_select_fts = """SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                           m.sender_display_name, m.formatted_time, m.create_time
                    FROM messages m
                    JOIN sessions s ON m.session_id = s.id
                    WHERE m.id IN (
                        SELECT rowid FROM messages_fts 
                        WHERE messages_fts MATCH ?
                    )"""
db = db.replace(old_select_fts, new_select_fts, 1)
print('1c. SELECT + session_type (FTS branch)')

# 1d. SELECT 增加 s.type — only_sender 分支
old_select_sender = """SELECT m.id, m.session_id, s.display_name as session_name, m.content, 
                       m.sender_display_name, m.formatted_time, m.create_time
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                WHERE 1=1"""
new_select_sender = """SELECT m.id, m.session_id, s.display_name as session_name, s.type as session_type, m.content, 
                       m.sender_display_name, m.formatted_time, m.create_time
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                WHERE 1=1"""
db = db.replace(old_select_sender, new_select_sender, 1)
print('1d. SELECT + session_type (sender branch)')

# 1e. 在 session_id 过滤后添加 session_type 过滤
old_filter_pos = """if session_id:
            base_query += " AND m.session_id = ?"
            params.append(session_id)"""
new_filter_pos = """if session_id:
            base_query += " AND m.session_id = ?"
            params.append(session_id)

        if session_type and session_type != '全部':
            base_query += " AND s.type = ?"
            params.append(session_type)"""
db = db.replace(old_filter_pos, new_filter_pos, 1)
print('1e. session_type filter added')

# 1f. 修改 session_stats 统计，增加 type 信息
old_stats = """for match in filtered_matches:
            if match['session_id']:
                session_key = f"{match['session_id']}-{match['session_name']}"
                if session_key not in session_stats:
                    session_stats[session_key] = {
                        'id': match['session_id'],
                        'name': match['session_name'],
                        'count': 0
                    }
                session_stats[session_key]['count'] += 1"""
new_stats = """# 统计: 按会话
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
            type_stats[t] += 1"""
db = db.replace(old_stats, new_stats, 1)
print('1f. type_stats added')

# 1g. 修改返回值，增加 type_stats
old_return = '''return {
            "total": total_results,
            "results": paginated_results,
            "limit": limit,
            "offset": offset,
            "session_stats": session_stats_list,
            "sender_stats": sender_stats_list
        }'''
new_return = '''type_stats_list = [{'type': t, 'count': c} for t, c in sorted(type_stats.items(), key=lambda x: x[1], reverse=True)]
        return {
            "total": total_results,
            "results": paginated_results,
            "limit": limit,
            "offset": offset,
            "session_stats": session_stats_list,
            "sender_stats": sender_stats_list,
            "type_stats": type_stats_list
        }'''
db = db.replace(old_return, new_return, 1)
print('1g. type_stats in return')

with open('wechat_db.py', 'w', encoding='utf-8') as f:
    f.write(db)
print('wechat_db.py written')

# ═══════════════════════════════════════════════════════════
# 2. 修改 wechat_api.py — 增加 session_type 参数
# ═══════════════════════════════════════════════════════════
with open('wechat_api.py', 'r', encoding='utf-8') as f:
    api = f.read()

old_api_sig = '''    only_sender: bool = False
) -> HTTPException:'''
new_api_sig = '''    only_sender: bool = False,
    session_type: Optional[str] = Query(None, description="会话类型过滤：群聊/私聊/公众号，不传则搜全部")
) -> HTTPException:'''
api = api.replace(old_api_sig, new_api_sig, 1)
print('2. API session_type param added')

old_api_call = '''            filters, sort_by, sort_order, start_time, end_time, show_context, only_sender
        )'''
new_api_call = '''            filters, sort_by, sort_order, start_time, end_time, show_context, only_sender,
            session_type
        )'''
api = api.replace(old_api_call, new_api_call, 1)
print('2b. API function call updated')

with open('wechat_api.py', 'w', encoding='utf-8') as f:
    f.write(api)
print('wechat_api.py written')

# ═══════════════════════════════════════════════════════════
# 3. 修改 templates/index.html — 前端 UI + 搜索逻辑 + 分组展示
# ═══════════════════════════════════════════════════════════
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ── 3a. wechatState 增加搜索相关状态 ──
old_state = '''// 搜索结果分页状态
            searchLimit: 50,
            searchOffset: 0,
            searchTotal: 0,
            searchResults: []'''
new_state = '''// 搜索结果分页状态
            searchLimit: 50,
            searchOffset: 0,
            searchTotal: 0,
            searchResults: [],
            // 全量搜索: 搜索范围
            searchScope: 'all',      // 'session'=指定会话, 'all'=全部
            searchSessionType: '',   // '群聊'/'私聊'/'公众号'/''=全部
            searchTypeStats: []      // 类型统计'''
html = html.replace(old_state, new_state, 1)
print('3a. wechatState updated')

# ── 3b. 搜索 HTML 区域 — 在会话选择上方添加搜索范围切换 ──
old_search_html = '''                                <div class="analysis-control-row" style="flex-direction: column; align-items: flex-start; gap: 6px;">
                                    <label style="font-weight: 500;">选择会话</label>
                                    <select id="wechat-session-type-filter" class="analysis-select" style="width: 90px; box-sizing: border-box;">
                                        <option value="all">全部</option>
                                        <option value="群聊">群聊</option>
                                        <option value="私聊">私聊</option>
                                        <option value="公众号">公众号</option>
                                    </select>
                                    </div>
                                    <select id="wechat-session-select" class="analysis-select" style="width: 100%;">
                                        <option value="">-- 正在读取 --</option>
                                    </select>
                                </div>'''
new_search_html = '''                                <div class="analysis-control-row" style="flex-direction: column; align-items: flex-start; gap: 6px;">
                                    <label style="font-weight: 500;">搜索范围</label>
                                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                        <label style="display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 0.85rem;">
                                            <input type="radio" name="searchScope" value="all" checked onclick="toggleSearchScope('all')" style="accent-color: var(--accent-color, #38bdf8);"> 🔍 全量检索
                                        </label>
                                        <label style="display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 0.85rem;">
                                            <input type="radio" name="searchScope" value="session" onclick="toggleSearchScope('session')" style="accent-color: var(--accent-color, #38bdf8);"> 💬 指定会话
                                        </label>
                                    </div>
                                    <!-- 全量检索: 类型过滤 -->
                                    <div id="search-type-filter" style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px;">
                                        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-size:0.78rem;">
                                            <input type="radio" name="searchSessionType" value="" checked onclick="toggleSearchSessionType('')" style="accent-color:var(--accent-color,#38bdf8);"> 全部
                                        </label>
                                        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-size:0.78rem;">
                                            <input type="radio" name="searchSessionType" value="群聊" onclick="toggleSearchSessionType('群聊')" style="accent-color:var(--accent-color,#38bdf8);"> 👥 群聊
                                        </label>
                                        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-size:0.78rem;">
                                            <input type="radio" name="searchSessionType" value="私聊" onclick="toggleSearchSessionType('私聊')" style="accent-color:var(--accent-color,#38bdf8);"> 👤 私聊
                                        </label>
                                        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;font-size:0.78rem;">
                                            <input type="radio" name="searchSessionType" value="公众号" onclick="toggleSearchSessionType('公众号')" style="accent-color:var(--accent-color,#38bdf8);"> 📢 公众号
                                        </label>
                                    </div>
                                </div>
                                <div class="analysis-control-row" id="session-select-container" style="flex-direction: column; align-items: flex-start; gap: 6px; display: none;">
                                    <label style="font-weight: 500;">选择会话</label>
                                    <select id="wechat-session-select" class="analysis-select" style="width: 100%;">
                                        <option value="">-- 正在读取 --</option>
                                    </select>
                                </div>'''
html = html.replace(old_search_html, new_search_html, 1)
print('3b. Search HTML updated')

# ── 3c. searchWechatMessages 函数 — 增加 session_type 处理 ──
# 找到函数中的 URL 构建部分，替换整个 try 块
old_search_func_start = '''        async function searchWechatMessages(loadMore = false) {
            const keyword = document.getElementById('wechat-keyword-input').value.trim();
            const sender = document.getElementById('wechat-sender-input').value.trim();
            const sessionId = document.getElementById('wechat-session-select').value;
            const stats = document.getElementById('wechat-feed-stats');
            const feed = document.getElementById('wechat-bubble-feed');

            if (!keyword && !sender) {
                alert('检索必须输入检索词或指定发言人昵称');
                return;
            }

            if (!loadMore) {
                // 新搜索,重置状态
                wechatState.isSearchMode = true;
                wechatState.keyword = keyword;
                wechatState.sender = sender;
                wechatState.searchOffset = 0;
                wechatState.searchResults = [];

                stats.textContent = '🔍 正在检索...';
                feed.innerHTML = '<div style="text-align: center; color: var(--text-muted, #64748b); margin-top: 60px;">正在执行全文检索中...</div>';
            } else {
                // 加载更多,追加结果
                if (wechatState.isLoading) return;
                stats.textContent = '🔍 正在加载更多...';
            }

            wechatState.isLoading = true;

            const st = getSelectedStartTime();
            const et = getSelectedEndTime();

            try {
                let url = `/api/wechat/search/keyword?keyword=${encodeURIComponent(keyword)}&only_sender=${sender ? 'true' : 'false'}&limit=${wechatState.searchLimit}&offset=${wechatState.searchOffset}`;
                if (sessionId) {
                    url += `&session_id=${sessionId}`;
                }
                if (sender) {
                    url += `&sender_display_name=${encodeURIComponent(sender)}`;
                }
                if (st) url += `&start_time=${st}`;
                if (et) url += `&end_time=${et}`;

                const res = await fetch(url);
                const result = await res.json();
                if (!result.success) {
                    stats.textContent = '❌ 检索失败';
                    feed.innerHTML = '<div style="text-align: center; color: #ef4444; margin-top: 60px;">检索失败</div>';
                    wechatState.isLoading = false;
                    return;
                }

                const items = result.data.results || [];
                wechatState.searchTotal = result.data.total;'''

new_search_func_start = '''        async function searchWechatMessages(loadMore = false) {
            const keyword = document.getElementById('wechat-keyword-input').value.trim();
            const sender = document.getElementById('wechat-sender-input').value.trim();
            const sessionId = document.getElementById('wechat-session-select').value;
            const scope = wechatState.searchScope;
            const sessionType = wechatState.searchSessionType;
            const stats = document.getElementById('wechat-feed-stats');
            const feed = document.getElementById('wechat-bubble-feed');

            if (!keyword && !sender) {
                alert('检索必须输入检索词或指定发言人昵称');
                return;
            }

            if (!loadMore) {
                wechatState.isSearchMode = true;
                wechatState.keyword = keyword;
                wechatState.sender = sender;
                wechatState.searchOffset = 0;
                wechatState.searchResults = [];
                wechatState.searchTypeStats = [];

                const scopeLabel = scope === 'all' ? (sessionType || '全部') : '指定会话';
                stats.textContent = `🔍 正在检索 [${scopeLabel}]...`;
                feed.innerHTML = '<div style="text-align: center; color: var(--text-muted, #64748b); margin-top: 60px;">正在执行全文检索中...</div>';
            } else {
                if (wechatState.isLoading) return;
                stats.textContent = '🔍 正在加载更多...';
            }

            wechatState.isLoading = true;
            const st = getSelectedStartTime();
            const et = getSelectedEndTime();

            try {
                let url = `/api/wechat/search/keyword?keyword=${encodeURIComponent(keyword)}&only_sender=${sender ? 'true' : 'false'}&limit=${wechatState.searchLimit}&offset=${wechatState.searchOffset}`;
                if (scope === 'session' && sessionId) {
                    url += `&session_id=${sessionId}`;
                }
                if (scope === 'all' && sessionType) {
                    url += `&session_type=${encodeURIComponent(sessionType)}`;
                }
                if (sender) {
                    url += `&sender_display_name=${encodeURIComponent(sender)}`;
                }
                if (st) url += `&start_time=${st}`;
                if (et) url += `&end_time=${et}`;

                const res = await fetch(url);
                const result = await res.json();
                if (!result.success) {
                    stats.textContent = '❌ 检索失败';
                    feed.innerHTML = '<div style="text-align: center; color: #ef4444; margin-top: 60px;">检索失败</div>';
                    wechatState.isLoading = false;
                    return;
                }

                const items = result.data.results || [];
                wechatState.searchTotal = result.data.total;
                // 保存类型统计
                wechatState.searchTypeStats = result.data.type_stats || [];'''
html = html.replace(old_search_func_start, new_search_func_start, 1)
print('3c. searchWechatMessages URL building updated')

# ── 3d. 渲染部分 — 按类型分组展示 ──
old_render_results = '''                // 计算分页状态
                const loadedCount = wechatState.searchResults.length;
                const hasMore = loadedCount < wechatState.searchTotal;

                stats.textContent = `共搜索到 ${wechatState.searchTotal} 条匹配结果,已加载 ${loadedCount} 条`;

                // 渲染消息
                renderWechatBubbles(wechatState.searchResults, keyword, true);'''
new_render_results = '''                // 计算分页状态
                const loadedCount = wechatState.searchResults.length;
                const hasMore = loadedCount < wechatState.searchTotal;

                // 类型统计信息
                const typeStats = wechatState.searchTypeStats;
                let statsText = `共搜索到 ${wechatState.searchTotal} 条`;
                if (typeStats.length > 0 && wechatState.searchScope === 'all' && !wechatState.searchSessionType) {
                    const parts = typeStats.map(t => `${t.type}${t.count}条`).join(' / ');
                    statsText += ` (${parts})`;
                } else if (wechatState.searchScope === 'all' && wechatState.searchSessionType) {
                    statsText += ` [${wechatState.searchSessionType}]`;
                }
                stats.textContent = statsText + `，已加载 ${loadedCount} 条`;

                // 按类型分组渲染
                renderWechatBubblesGrouped(wechatState.searchResults, keyword, wechatState.searchScope === 'all' && !wechatState.searchSessionType);'''
html = html.replace(old_render_results, new_render_results, 1)
print('3d. Results grouped rendering')

# ── 3e. 添加 toggleSearchScope 和 renderWechatBubblesGrouped 函数 ──
# 在 searchWechatMessages 函数之前插入

old_func_insert_point = '''        // 检索消息 (FTS + Senders)
        async function searchWechatMessages(loadMore = false) {'''
new_funcs = '''        // 切换搜索范围: 全量 vs 指定会话
        function toggleSearchScope(scope) {
            wechatState.searchScope = scope;
            const typeFilter = document.getElementById('search-type-filter');
            const sessionContainer = document.getElementById('session-select-container');
            if (scope === 'all') {
                if (typeFilter) typeFilter.style.display = 'flex';
                if (sessionContainer) sessionContainer.style.display = 'none';
            } else {
                if (typeFilter) typeFilter.style.display = 'none';
                if (sessionContainer) sessionContainer.style.display = 'flex';
            }
        }

        // 切换会话类型过滤
        function toggleSearchSessionType(type) {
            wechatState.searchSessionType = type;
        }

        // 按类型分组渲染搜索结果 (全量搜索时使用)
        function renderWechatBubblesGrouped(messages, keyword, groupByType) {
            const feed = document.getElementById('wechat-bubble-feed');
            feed.innerHTML = '';

            if (!messages || messages.length === 0) {
                feed.innerHTML = '<div style="text-align:center;color:var(--text-muted,#64748b);margin-top:60px;">未找到匹配结果</div>';
                return;
            }

            const typeLabelMap = { '群聊': '👥', '私聊': '👤', '公众号': '📢', '未知': '❓' };
            const typeColorMap = { '群聊': '#8b5cf6', '私聊': '#38bdf8', '公众号': '#f59e0b', '未知': '#94a3b8' };

            if (!groupByType) {
                renderWechatBubbles(messages, keyword, true);
                return;
            }

            // 按 session_type 分组
            const groups = {};
            for (const msg of messages) {
                const t = msg.session_type || '未知';
                if (!groups[t]) groups[t] = [];
                groups[t].push(msg);
            }

            const typeOrder = ['群聊', '私聊', '公众号', '未知'];
            const sortedTypes = typeOrder.filter(t => groups[t]).concat(Object.keys(groups).filter(t => !typeOrder.includes(t)));

            for (const typeName of sortedTypes) {
                const msgs = groups[typeName];
                const icon = typeLabelMap[typeName] || '💬';
                const color = typeColorMap[typeName] || '#94a3b8';

                // 类型分隔标题
                const header = document.createElement('div');
                header.className = 'wechat-group-header';
                header.style.cssText = `display:flex;align-items:center;gap:8px;padding:10px 16px;margin:16px 0 8px;background:${color}18;border:1px solid ${color}40;border-radius:8px;font-size:0.88rem;font-weight:600;color:${color};`;
                header.innerHTML = `<span style="font-size:1.1rem;">${icon}</span> ${typeName} <span style="margin-left:auto;font-size:0.78rem;opacity:0.75;">${msgs.length} 条结果</span>`;
                feed.appendChild(header);

                // 渲染该组消息
                renderWechatBubbles(msgs, keyword, true);
            }
        }

        // 检索消息 (FTS + Senders)
        async function searchWechatMessages(loadMore = false) {'''
html = html.replace(old_func_insert_point, new_funcs, 1)
print('3e. toggleSearchScope + renderWechatBubblesGrouped inserted')

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('templates/index.html written')

# ═══════════════════════════════════════════════════════════
# 4. 验证
# ═══════════════════════════════════════════════════════════
print('\n=== Verification ===')

with open('wechat_db.py', 'r', encoding='utf-8') as f:
    db_check = f.read()
checks = [
    ('session_type in sig', 'session_type: Optional[str]' in db_check),
    ('s.type in SELECT', "s.type as session_type" in db_check),
    ('session_type filter', '" AND s.type = ?"' in db_check),
    ('type_stats dict', 'type_stats = {}' in db_check),
    ('type_stats in return', '"type_stats": type_stats_list' in db_check),
]
for name, ok in checks:
    print(f'  {"PASS" if ok else "FAIL"}: wechat_db.py — {name}')

with open('wechat_api.py', 'r', encoding='utf-8') as f:
    api_check = f.read()
checks2 = [
    ('session_type param', 'session_type: Optional[str]' in api_check),
    ('passed to db func', 'session_type' in api_check),
]
for name, ok in checks2:
    print(f'  {"PASS" if ok else "FAIL"}: wechat_api.py — {name}')

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html_check = f.read()
checks3 = [
    ('searchScope in state', 'searchScope:' in html_check),
    ('searchSessionType in state', 'searchSessionType:' in html_check),
    ('toggleSearchScope func', 'function toggleSearchScope' in html_check),
    ('renderWechatBubblesGrouped', 'function renderWechatBubblesGrouped' in html_check),
    ('search-type-filter HTML', 'search-type-filter' in html_check),
    ('session_type in API URL', 'session_type=' in html_check),
    ('type_stats display', 'searchTypeStats' in html_check),
]
for name, ok in checks3:
    print(f'  {"PASS" if ok else "FAIL"}: index.html — {name}')

print('\nDone!')
