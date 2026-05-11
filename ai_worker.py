import os
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
    """流式对话接口"""
    if request.model_id and request.model_id != summarizer.current_model_id:
        summarizer.switch_model(request.model_id)
    
    async def generate():
        for token in summarizer.chat_stream(request.messages):
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

