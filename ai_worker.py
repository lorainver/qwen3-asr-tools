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
if search_enabled:
    searcher = get_searcher(serper_api_key if serper_api_key else None)
    logger.info(f"联网搜索已启用 (Serper API: {'已配置' if serper_api_key else '未配置，使用 DuckDuckGo'})")
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
    enable_search: Optional[bool] = False  # 是否启用联网搜索

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
    """流式对话接口 - 支持联网搜索"""
    if request.model_id and request.model_id != summarizer.current_model_id:
        summarizer.switch_model(request.model_id)
    
    # 如果启用联网搜索，先搜索并注入上下文
    search_context = ""
    if request.enable_search and searcher:
        # 从最后一条用户消息提取搜索关键词
        last_user_msg = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        if last_user_msg:
            max_results = config.get('search.max_results', 5)
            results = searcher.search(last_user_msg, max_results=max_results)
            search_context = searcher.format_for_llm(results)
            
            if search_context:
                logger.info(f"🌐 联网搜索已注入上下文 ({len(results)} 条结果)")
            else:
                logger.warning("🌐 联网搜索无结果")
    
    # 如果有搜索上下文，优化注入逻辑：采用“知识优先级”模式
    messages = []
    original_messages = request.messages
    for i, msg in enumerate(original_messages):
        new_msg = msg.copy()
        if i == len(original_messages) - 1 and msg.get("role") == "user" and search_context:
            # 采用更具强制性的 Prompt 结构
            injected_content = f"""【实时联网搜索参考资料】
{search_context}
--------------------------
【重要指令】
你现在的身份是具备联网能力的 AI 助手。请务必优先根据上方提供的“实时联网搜索参考资料”来回答问题。
如果搜索结果与你的常识不符，请以搜索结果为准。如果搜索结果中包含诗词作者、时间、地点等事实，请直接引用。

用户当前提问：{msg.get('content')}"""
            new_msg["content"] = injected_content
            logger.info(f"🚀 联网搜索上下文已就近注入 (采用强制指令模式, 长度: {len(injected_content)})")
        messages.append(new_msg)
    
    async def generate():
        # 如果有搜索结果，先发送搜索状态
        if search_context:
            yield f"data: {json.dumps({'type': 'search', 'status': 'done'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)
        
        for token in summarizer.chat_stream(messages):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            # 添加微小延迟，确保每个 token 分开发送（打字机效果）
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"
    
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
    # 1. 自动切换模型
    if request.model and request.model != summarizer.current_model_id:
        logger.info(f"[OpenAI API] 切换模型至: {request.model}")
        summarizer.switch_model(request.model)

    # 2. 流式响应
    if request.stream:
        async def openai_stream_generator():
            request_id = f"chatcmpl-{uuid.uuid4()}"
            created_time = int(time.time())
            
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
    uvicorn.run(app, host="127.0.0.1", port=8001)

