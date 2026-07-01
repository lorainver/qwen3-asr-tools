import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from wechat_db import wechat_db
from wechat_ai_analyzer import wechat_ai_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat", tags=["微信分析"])

# ==================== 请求/响应模型 ====================

class SessionAnalyzeRequest(BaseModel):
    session_id: int
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    use_cache: bool = True

class UserAnalyzeRequest(BaseModel):
    username: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    use_cache: bool = True

class ThemeAnalyzeRequest(BaseModel):
    group_name: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    use_cache: bool = True

class RelationsAnalyzeRequest(BaseModel):
    username: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    use_cache: bool = True

class Top5AnalyzeRequest(BaseModel):
    session_id: int
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    use_cache: bool = True

class ChatAnalyzeRequest(BaseModel):
    query: str
    context: List[Dict[str, Any]]
    use_cache: bool = True

class MemberRemarkRequest(BaseModel):
    wxid: str
    remark: str
    tags: Optional[str] = None

class SyncRemarksRequest(BaseModel):
    session_id: int
    overwrite: bool = False
    tag: Optional[str] = None

# ==================== 接口定义 ====================

@router.get("/sessions")
async def get_sessions(type: Optional[str] = None):
    try:
        sessions = wechat_db.get_all_sessions(type)
        return {"success": True, "data": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session(
    session_id: int,
    limit: int = 100,
    offset: int = 0,
    filters: Optional[List[str]] = Query(None),
    sort_order: str = "asc",
    start_time: Optional[int] = None,
    end_time: Optional[int] = None
):
    try:
        session_info = wechat_db.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
            
        messages = wechat_db.get_session_messages(
            session_id, limit, offset, filters, sort_order, start_time, end_time
        )
        
        all_filtered = wechat_db.get_session_messages(
            session_id, limit=0, offset=0, filters=filters, start_time=start_time, end_time=end_time
        )
        
        return {
            "success": True,
            "session": session_info,
            "messages": messages,
            "filtered_message_count": len(all_filtered)
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/message/{message_id}/position")
async def get_message_position(
    message_id: int,
    filters: Optional[List[str]] = Query(None),
    start_time: Optional[int] = None,
    end_time: Optional[int] = None
):
    try:
        pos = wechat_db.get_message_position(message_id, filters, start_time, end_time)
        if not pos:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True, "data": pos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/username")
async def search_by_username(
    username: str,
    limit: int = 10,
    offset: int = 0
):
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    try:
        results = wechat_db.search_by_username(username, limit, offset)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/keyword")
async def search_by_keyword(
    keyword: str = "",
    session_id: Optional[int] = None,
    sender_display_name: Optional[str] = None,
    context_lines: int = 3,
    limit: int = 50,
    offset: int = 0,
    filters: Optional[List[str]] = Query(None),
    sort_by: str = "time",
    sort_order: str = "desc",
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    show_context: bool = False,
    only_sender: bool = False,
    session_type: Optional[str] = Query(None, description="会话类型过滤：群聊/私聊/公众号，不传则搜全部")
):
    if not keyword and not only_sender:
        raise HTTPException(status_code=400, detail="Keyword or only_sender filter is required")
    try:
        results = wechat_db.search_by_keyword(
            keyword, session_id, sender_display_name, context_lines, limit, offset,
            filters, sort_by, sort_order, start_time, end_time, show_context, only_sender,
            session_type
        )
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/stats")
async def search_stats_only(
    keyword: str = "",
    sender_display_name: Optional[str] = None,
    session_type: Optional[str] = Query(None, description="会话类型过滤：群聊/私聊/公众号，不传则搜全部"),
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    only_sender: bool = False
):
    """只返回搜索结果的统计信息（按会话分组），不返回具体消息，用于首屏秒开"""
    if not keyword and not only_sender:
        raise HTTPException(status_code=400, detail="Keyword or only_sender filter is required")
    try:
        results = wechat_db.search_by_keyword(
            keyword=keyword, session_id=None, sender_display_name=sender_display_name,
            context_lines=0, limit=0, offset=0, filters=None, sort_by="time", sort_order="desc",
            start_time=start_time, end_time=end_time, show_context=False, only_sender=only_sender,
            session_type=session_type
        )
        # 只返回统计信息，不返回具体消息
        return {
            "success": True,
            "data": {
                "total": results["total"],
                "session_stats": results["session_stats"],
                "type_stats": results["type_stats"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats():
    try:
        cursor = wechat_db.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total_sessions FROM sessions")
        total_sessions = cursor.fetchone()["total_sessions"]
        
        cursor.execute("SELECT COUNT(*) as total_messages FROM messages")
        total_messages = cursor.fetchone()["total_messages"]
        
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()["total_users"]
        
        cursor.execute("SELECT COUNT(*) as group_chats FROM sessions WHERE type = '群聊'")
        group_chats = cursor.fetchone()["group_chats"]
        
        cursor.execute("SELECT COUNT(*) as private_chats FROM sessions WHERE type = '私聊'")
        private_chats = cursor.fetchone()["private_chats"]
        
        return {
            "success": True,
            "data": {
                "total_sessions": total_sessions,
                "total_messages": total_messages,
                "total_users": total_users,
                "group_chats": group_chats,
                "private_chats": private_chats
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AI 分析接口 ====================

@router.post("/analyze/session")
async def analyze_session(req: SessionAnalyzeRequest):
    result = wechat_ai_analyzer.analyze_session(
        req.session_id, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/analyze/user")
async def analyze_user(req: UserAnalyzeRequest):
    result = wechat_ai_analyzer.analyze_user(
        req.username, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/analyze/user_mbti")
async def analyze_user_mbti(req: UserAnalyzeRequest):
    result = wechat_ai_analyzer.analyze_user_mbti(
        req.username, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))


@router.post("/analyze/theme")
async def analyze_theme(req: ThemeAnalyzeRequest):
    result = wechat_ai_analyzer.analyze_group_theme(
        req.group_name, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/analyze/relations")
async def analyze_relations(req: RelationsAnalyzeRequest):
    result = wechat_ai_analyzer.analyze_user_relations(
        req.username, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/analyze/top5")
async def analyze_top5(req: Top5AnalyzeRequest):
    result = wechat_ai_analyzer.analyze_top5(
        req.session_id, req.start_time, req.end_time, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/analyze/chat")
async def analyze_chat(req: ChatAnalyzeRequest):
    result = wechat_ai_analyzer.chat_analyze(
        req.query, req.context, req.use_cache
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "AI 分析失败"))

@router.post("/cache/clear")
async def clear_ai_cache():
    """清除 AI 分析缓存"""
    try:
        wechat_ai_analyzer.cache = {}
        return {"success": True, "message": "缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/status")
async def get_cache_status():
    """获取缓存状态"""
    try:
        cache_count = len(wechat_ai_analyzer.cache)
        cache_keys = list(wechat_ai_analyzer.cache.keys())
        return {
            "success": True,
            "data": {
                "count": cache_count,
                "keys": cache_keys,
                "ttl": wechat_ai_analyzer.cache_ttl
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 群成员分析接口 ====================

@router.get("/members/overlap")
async def get_members_overlap(
    session_id: int, 
    exclude_wxids: Optional[str] = "loeainve,osugaro"
):
    try:
        excludes = [x.strip() for x in exclude_wxids.split(",") if x.strip()]
        res = wechat_db.get_group_member_overlap(session_id, excludes)
        if "error" in res:
            raise HTTPException(status_code=400, detail=res["error"])
        return res
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/members/profile")
async def get_members_profile(wxid: str = "", name: str = ""):
    try:
        res = wechat_db.get_member_profile(wxid, name=name)
        if "error" in res:
            raise HTTPException(status_code=400, detail=res["error"])
        return {"success": True, "profile": res}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/members/search")
async def search_members(keyword: str):
    try:
        res = wechat_db.search_group_members(keyword)
        return {"success": True, "results": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/members/reload")
async def reload_members_log():
    try:
        log_path = r"D:\Programs\EchoTrace\documents\处理日志.txt"
        count = wechat_db.import_group_members_log(log_path)
        return {"success": True, "message": f"成功重新加载 {count} 条群友数据"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/members/sync-cli")
async def sync_members_cli():
    try:
        count = wechat_db.import_group_members_via_cli()
        return {"success": True, "message": f"成功通过 wechat-cli 同步 {count} 条群友数据"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/members/remark")
async def save_member_remark(req: MemberRemarkRequest):
    try:
        wechat_db.save_member_remark(req.wxid, req.remark, req.tags)
        return {"success": True, "message": "备注与标签更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/members/sync-group")
async def sync_group_remarks(req: SyncRemarksRequest):
    try:
        count = wechat_db.sync_group_members_to_remarks(req.session_id, req.overwrite, req.tag)
        return {"success": True, "message": f"成功同步了 {count} 位实名群友的备注与标签"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/members/remarks")
async def get_all_member_remarks():
    try:
        remarks = wechat_db.get_all_member_remarks()
        return {"success": True, "remarks": remarks, "total": len(remarks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/members/remark/{wxid}")
async def delete_member_remark(wxid: str):
    try:
        ok = wechat_db.delete_member_remark(wxid)
        if ok:
            return {"success": True, "message": "备注已删除"}
        else:
            raise HTTPException(status_code=404, detail="未找到该备注")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/members/solicitation-suggestions")
async def get_solicitation_suggestions(wxid: str, session_id: Optional[int] = None):
    try:
        suggestions = wechat_db.get_solicitation_suggestions(wxid, session_id)
        return {"success": True, "suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


