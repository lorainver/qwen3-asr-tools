import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import sys
import json
import time
import uuid
import logging
import asyncio
import re
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
    enable_think: bool = True  # 是否启用深度思考（默认开启）
    search_optimize_prompt: Optional[str] = None # 自定义优化提示词

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class SummarizeRequest(BaseModel):
    text: str
    prompt_type: Optional[str] = "summarize"
    target_lang: Optional[str] = None  # 目标语言，仅用于翻译模式

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
    logger.info(f"📩 收到请求: search={request.enable_search}, optimize={request.optimize_search}, think={request.enable_think}")
    
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
            for token in summarizer.chat_stream(messages, enable_think=request.enable_think):
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

# ========== 翻译辅助函数 ==========

def chunk_text_for_translation(text, max_chunk_size=3000):
    """将长文本按段落拆分为块，每块不超过 max_chunk_size 字符
    
    拆分策略：
    1. 优先按双换行（段落边界）拆分
    2. 单段落过长时按句号/问号/感叹号（句子边界）拆分
    3. 单句超长时按 max_chunk_size 硬切
    """
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > max_chunk_size:
            chunks.append(current)
            current = para
        else:
            current = (current + '\n\n' + para) if current else para
    
    if current:
        chunks.append(current)
    
    # 处理超长段落：按句子边界拆分
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chunk_size:
            final_chunks.append(chunk)
        else:
            sentences = re.split(r'(?<=[。！？.!?])\s*', chunk)
            sub_chunk = ""
            for sent in sentences:
                if sub_chunk and len(sub_chunk) + len(sent) + 1 > max_chunk_size:
                    final_chunks.append(sub_chunk)
                    sub_chunk = sent
                else:
                    sub_chunk = (sub_chunk + ' ' + sent) if sub_chunk else sent
            if sub_chunk:
                final_chunks.append(sub_chunk)
    
    # 极端情况：单句超长，硬切
    result = []
    for chunk in final_chunks:
        if len(chunk) <= max_chunk_size:
            result.append(chunk)
        else:
            for i in range(0, len(chunk), max_chunk_size):
                result.append(chunk[i:i + max_chunk_size])
    
    return result if result else [text]


LANG_MAP = {
    'zh': '中文',
    'en': '英文',
    'ja': '日文',
    'ko': '韩文',
    'fr': '法文',
    'de': '德文',
}

def get_translate_prompt(target_lang='zh'):
    """根据目标语言动态生成翻译提示词"""
    target = LANG_MAP.get(target_lang, '中文')
    return (
        f"你是一个专业的翻译专家。请将以下内容翻译成流畅的{target}，"
        f"要求在保留原意的基础上，使其更符合{target}的表达习惯。"
        f"如果是技术内容，请确保专业术语翻译准确。"
        f"只需输出翻译后的内容，不要添加任何解释、注释或前后说明。"
    )


@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    """文本总结接口 - 支持多种提示词预设，翻译模式支持分块和目标语言"""
    logger.info(f"📝 收到总结请求: type={request.prompt_type}, 长度={len(request.text)}, target_lang={request.target_lang}")
    
    # ========== 翻译模式：分块 + 目标语言 + 增大输出上限 ==========
    if request.prompt_type == 'translate':
        target_lang = request.target_lang or 'zh'
        system_prompt = get_translate_prompt(target_lang)
        text = request.text
        CHUNK_SIZE = 3000
        MAX_OUTPUT_TOKENS = 4096  # 翻译输出长度 ≈ 输入长度，远超默认 2048
        
        # 判断是否需要分块
        needs_chunking = len(text) > CHUNK_SIZE
        chunks = chunk_text_for_translation(text, CHUNK_SIZE) if needs_chunking else [text]
        total_chunks = len(chunks)
        
        logger.info(f"🌐 翻译模式: 目标={LANG_MAP.get(target_lang, '中文')}, 分块={needs_chunking}({total_chunks}块)")
        
        async def generate_translate():
            full_result = ""
            
            for i, chunk in enumerate(chunks):
                # 发送分块进度
                if needs_chunking:
                    yield json.dumps({
                        "status": "processing",
                        "message": f"正在翻译第 {i+1}/{total_chunks} 段...",
                        "chunk": i + 1,
                        "total_chunks": total_chunks
                    }) + "\n"
                else:
                    yield json.dumps({"status": "processing", "message": "正在翻译..."}) + "\n"
                await asyncio.sleep(0.01)
                
                chunk_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk}
                ]
                
                try:
                    chunk_result = ""
                    for token in summarizer.chat_stream(chunk_messages, max_new_tokens=MAX_OUTPUT_TOKENS):
                        chunk_result += token
                        full_result += token
                        yield json.dumps({"status": "streaming", "delta": token}) + "\n"
                        await asyncio.sleep(0.01)
                    
                    # 分块间添加换行（非最后一块）
                    if i < total_chunks - 1:
                        full_result += "\n\n"
                        yield json.dumps({"status": "streaming", "delta": "\n\n"}) + "\n"
                except Exception as e:
                    logger.error(f"翻译第 {i+1} 段失败: {e}")
                    yield json.dumps({"status": "error", "message": f"翻译第 {i+1}/{total_chunks} 段失败: {str(e)}"}) + "\n"
                    break
            
            yield json.dumps({"status": "done", "result": full_result}) + "\n"
            
            # 清理 GPU 缓存
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
        
        return StreamingResponse(generate_translate(), media_type="text/plain")
    
    # ========== 通用模式：深度总结 / 待办提取 / 文案润色 ==========
    prompts = config.get('prompts', {})
    prompt_info = prompts.get(request.prompt_type, prompts.get('summarize', {}))
    system_prompt = prompt_info.get('content', "你是一个专业的AI助手。")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"以下是需要处理的文本内容：\n\n{request.text}"}
    ]
    
    async def generate():
        yield json.dumps({"status": "processing", "message": f"正在使用「{prompt_info.get('name', 'AI')}」模式进行处理..."}) + "\n"
        await asyncio.sleep(0.01)
        
        try:
            full_result = ""
            for token in summarizer.chat_stream(messages):
                full_result += token
                yield json.dumps({"status": "streaming", "delta": token}) + "\n"
                await asyncio.sleep(0.01)
            
            yield json.dumps({"status": "done", "result": full_result}) + "\n"
        except Exception as e:
            logger.error(f"总结失败: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"
        finally:
            import torch
            torch.cuda.empty_cache()

    return StreamingResponse(generate(), media_type="text/plain")

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

