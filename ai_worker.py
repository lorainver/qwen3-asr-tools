import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import sys
import json
import time
import uuid
import logging
import asyncio
from typing import List, Optional, Any, Dict, Union

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入我们的核心模型类
from summarizer import LongTextSummarizer
from web_searcher import get_searcher, reset_searcher
from config_loader import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Qwen3-ASR AI Worker")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化模型 (单例模式)
summarizer = LongTextSummarizer()

# 初始化搜索器
search_enabled = config.get('search.enabled', True)
serper_api_key = config.get('search.serper_api_key', '')
searxng_url = config.get('search.searxng_url', '')

if search_enabled:
    searcher = get_searcher(
        serper_api_key if serper_api_key else None,
        searxng_url if searxng_url else None
    )
    if searxng_url:
        logger.info(f"联网搜索已启用 (优先使用私有 SearXNG: {searxng_url})")
    else:
        logger.info(f"联网搜索已启用 (使用备用引擎: {'Serper' if serper_api_key else 'DuckDuckGo'})")
else:
    searcher = None

# ========== Pydantic 模型 (简化版，避免 Pydantic 验证错误) ==========

class OpenAIModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 1677610602
    owned_by: str = "qwen"

class OpenAIModelList(BaseModel):
    object: str = "list"
    data: List[OpenAIModelInfo]

class OpenAICompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]] # 使用字典列表，避开嵌套解析问题
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = 2048

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model_id: Optional[str] = None
    enable_search: Optional[bool] = True  # 是否启用联网搜索（默认开启）
    optimize_search: bool = True  # 是否开启搜索优化（默认开启）
    search_optimize_prompt: Optional[str] = None # 自定义优化提示词

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class SwitchModelRequest(BaseModel):
    model_id: str

# ========== API 路由 ==========

@app.get("/health")
async def health_check():
    return {"status": "ok", "model": summarizer.current_model_id}

# 非流式 不用
# @app.post("/api/chat")
# async def api_chat(request: ChatRequest):
#     """非流式对话接口"""
#     if request.model_id and request.model_id != summarizer.current_model_id:
#         summarizer.switch_model(request.model_id)
#     
#     response = summarizer.chat(request.messages)
#     return {"response": response, "model": summarizer.current_model_id}

@app.post("/api/chat_stream")
async def api_chat_stream(request: ChatRequest):
    """流式对话接口 - 支持联网搜索及搜索优化"""
    logger.info(f"📩 收到请求: search={request.enable_search}, optimize={request.optimize_search}")
    
    if request.model_id and request.model_id != summarizer.current_model_id:
        summarizer.switch_model(request.model_id)
    
    # 记录输入长度
    total_chars = sum(len(str(m.get("content", ""))) for m in request.messages)
    logger.info(f"📊 [Request] 输入消息共 {len(request.messages)} 条, 总计 {total_chars} 字符")
    
    # 1. 处理联网搜索
    search_context = ""
    messages = request.messages.copy()
    
    if request.enable_search and searcher:
        # 获取最后一条用户消息
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break
        
        if last_user_msg:
            query_text = last_user_msg.get("content", "")
            search_query = query_text
            
            # --- 优化：Query 预处理 (关键词提取) ---
            # 只有当显式开启了优化且提问较长时才执行
            if request.optimize_search is True and len(query_text) > 10:
                logger.info(f"🧠 正在为提问进行 AI 关键词优化: '{query_text[:30]}...'")
                try:
                    # 使用更严格的 Prompt
                    # default_optimizer_prompt = f"请将以下问题提炼为 3 个最关键的搜索关键词，用空格隔开。要求：严禁使用序号，严禁换行，直接输出关键词。\n\n问题：{query_text}"
                    default_optimizer_prompt = f"这是用户发来的请求, 先提取里面具体查询的内容, 然后这部分内容提炼为几个最关键的搜索关键词，用空格隔开。要求：严禁使用序号，严禁换行，直接输出关键词。\n\n问题：{query_text}"
                    keyword_prompt = request.search_optimize_prompt.replace("{query}", query_text) if request.search_optimize_prompt else default_optimizer_prompt
                    
                    logger.debug(f"📝 优化 Prompt: {keyword_prompt}")
                    # 使用当前活动的模型生成
                    keywords = summarizer.chat([{"role": "user", "content": keyword_prompt}]).strip()
                    
                    # 强力清洗
                    keywords = keywords.replace("\n", " ").replace("\r", " ")
                    import re
                    keywords = re.sub(r'^\d+[\.、\s:-]+', '', keywords)
                    for prefix in ["关键词：", "关键词:", "Keywords:", "搜索词：", "Search:"]:
                        if keywords.startswith(prefix):
                            keywords = keywords[len(prefix):].strip()
                    keywords = keywords.replace('"', '').replace("'", "").strip()
                    
                    if keywords and len(keywords) < 100:
                        logger.info(f"🔍 [Query 优化成功] 最终关键词: '{keywords}'")
                        search_query = keywords
                except Exception as e:
                    logger.warning(f"⚠️ Query 优化失败: {e}")
            else:
                logger.info(f"⏭️ 跳过 AI 关键词优化 (原因: 开关={request.optimize_search}, 长度={len(query_text)})")

            # 执行搜索
            max_results = config.get('search.max_results', 8)
            search_results = searcher.search(search_query, max_results=max_results)
            search_context = searcher.format_for_llm(search_results)
            
            if search_context:
                logger.info(f"🌐 联网搜索已注入上下文 ({len(search_results)} 条结果)")
                # 注入上下文
                injected_content = f"""【实时联网搜索到的事实资料】
{search_context}

【回答要求】
1. 必须严格按照上述“事实资料”回答。
2. 如果资料中没提到的信息，不要脑补。


用户提问：{query_text}"""
                last_user_msg["content"] = injected_content
                logger.info(f"🚀 联网搜索上下文已就近注入 (长度: {len(injected_content)})")
    
    async def generate():
        # 如果有搜索结果，先发送搜索状态
        if search_context:
            yield f"data: {json.dumps({'type': 'search', 'status': 'done'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
        
        try:
            for token in summarizer.chat_stream(messages):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                # 添加微小延迟，确保每个 token 分开发送（打字机效果）
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"
        finally:
            # 自动清理显存碎片
            import torch
            torch.cuda.empty_cache()
            logger.debug("🧹 已触发显存碎片清理")
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/models")
async def api_models():
    return {
        "current": summarizer.get_current_model(),
        "available": summarizer.get_available_models()
    }

@app.post("/api/switch_model")
async def api_switch_model(request: SwitchModelRequest):
    success = summarizer.switch_model(request.model_id)
    if success:
        return {"status": "ok", "current_model": summarizer.get_current_model()}
    return {"status": "error", "message": f"未知模型: {request.model_id}"}

# ========== 联网搜索接口 ==========

@app.post("/api/search")
async def api_search(request: SearchRequest):
    """独立搜索接口 - 返回搜索结果"""
    if not search_enabled or not searcher:
        return {"status": "error", "message": "联网搜索未启用"}
    
    results = searcher.search(request.query, max_results=request.max_results)
    return {
        "status": "ok",
        "results": [{
            "title": r.title,
            "snippet": r.snippet,
            "url": r.url,
            "source": r.source
        } for r in results]
    }

@app.get("/api/search/status")
async def api_search_status():
    """获取搜索功能状态"""
    return {
        "enabled": search_enabled,
        "engine": "serper" if (serper_api_key and not searcher.serper_quota_exceeded) else "duckduckgo",
        "serper_quota_exceeded": searcher.serper_quota_exceeded if searcher else False
    }

# ========== OpenAI 兼容接口 ==========

@app.get("/v1/models")
async def v1_models():
    available = summarizer.get_available_models()
    return {
        "object": "list",
        "data": [{"id": m['id'], "object": "model", "created": 1677610602, "owned_by": "qwen"} for m in available]
    }

@app.post("/v1/chat/completions")
async def v1_chat_completions(request: OpenAICompletionRequest):
    # 0. 调试信息：打印远程请求内容
    last_msg = request.messages[-1]["content"] if request.messages else "None"
    logger.info(f"📥 [OpenAI API] 收到远程请求 (共 {len(request.messages)} 条消息)")
    logger.info(f"📝 远程消息预览: {last_msg[:50000]}...")

    # 1. 自动切换模型
    if request.model and request.model != summarizer.current_model_id:
        logger.info(f"[OpenAI API] 切换模型至: {request.model}")
        summarizer.switch_model(request.model)

    # 记录输入长度
    total_chars = sum(len(str(m.get("content", ""))) for m in request.messages)
    logger.info(f"📊 [OpenAI API] 输入消息共 {len(request.messages)} 条, 总计 {total_chars} 字符")

    # 2. 流式响应
    if request.stream:
        async def openai_stream_generator():
            request_id = f"chatcmpl-{uuid.uuid4()}"
            created_time = int(time.time())
            
            try:
                for token in summarizer.chat_stream(request.messages):
                    chunk = {
                        "id": request_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": summarizer.current_model_id,
                        "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                done_chunk = {
                    "id": request_id, "object": "chat.completion.chunk", "created": created_time,
                    "model": summarizer.current_model_id,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(done_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                import torch
                torch.cuda.empty_cache()
                logger.debug("🧹 [OpenAI API] 已触发显存碎片清理")

        return StreamingResponse(
            openai_stream_generator(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    # 3. 非流式响应
    else:
        response_text = summarizer.chat(request.messages)
        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": summarizer.current_model_id,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop"
            }]
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

