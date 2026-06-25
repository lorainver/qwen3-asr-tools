import os
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import sys
import json
import time
import uuid
import logging
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Any, Dict, Union

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入我们的核心模型类
from summarizer import LongTextSummarizer
from web_searcher import get_searcher, reset_searcher
from config_loader import config

# 知识库模块（延迟初始化，避免与 ASR 模型争抢显存）
from knowledge_api import router as kb_router
from knowledge_store import init_knowledge_base

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Qwen3-ASR AI Worker")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化模型 (单例模式)
summarizer = LongTextSummarizer()

# 线程池：将同步阻塞的 chat_stream 生成器桥接到异步 SSE 及并发任务
_stream_executor = ThreadPoolExecutor(max_workers=16)

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

# 挂载知识库 API 路由（知识库独立初始化，不影响 ASR 显存管理）
app.include_router(kb_router)
from knowledge_api import set_summarizer as _set_kb_summarizer
_set_kb_summarizer(summarizer)
# 初始化知识库（读取已有索引，使 KB API 立即可用）
init_knowledge_base(summarizer=summarizer)
logger.info("📚 知识库路由已挂载: /api/kb/*")

# 挂载微信分析 API 路由与分析器初始化
from wechat_api import router as wechat_router
from wechat_ai_analyzer import wechat_ai_analyzer
wechat_ai_analyzer.set_summarizer(summarizer)
app.include_router(wechat_router)
logger.info("💬 微信分析路由已挂载: /api/wechat/*")

# ========== Pydantic 模型 (简化版,避免 Pydantic 验证错误) ==========

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
    messages: List[Dict[str, Any]] # 使用字典列表,避开嵌套解析问题
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = 2048

class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model_id: Optional[str] = None
    enable_search: Optional[bool] = True  # 是否启用联网搜索(默认开启)
    optimize_search: bool = True  # 是否开启搜索优化(默认开启)
    enable_think: bool = True  # 是否启用深度思考(默认开启)
    search_optimize_prompt: Optional[str] = None # 自定义优化提示词

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class SummarizeRequest(BaseModel):
    text: str
    prompt_type: Optional[str] = "summarize"
    target_lang: Optional[str] = None  # 目标语言,仅用于翻译模式
    parallel: Optional[bool] = False
    chunk_size: Optional[int] = None

class SwitchModelRequest(BaseModel):
    model_id: str

class TranscribePathRequest(BaseModel):
    path: str
    language: Optional[str] = None
    model_size: Optional[str] = "1.7B"

@app.post("/api/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    model_size: Optional[str] = Form("1.7B"),
):
    """
    处理上传文件转录的流式端点 (AI Worker)
    """
    logger.info(f"🎤 AI Worker 收到上传文件转录请求: filename={file.filename}, language={language}, model_size={model_size}")
    
    # 1. 暂存到临时目录
    import tempfile
    temp_dir = tempfile.gettempdir()
    unique_id = uuid.uuid4().hex
    temp_file_path = os.path.join(temp_dir, f"upload_{unique_id}_{file.filename}")
    
    try:
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 对应 SRT 保存路径
        srt_path = temp_file_path + ".srt"
        
        # 2. 桥接为流式响应
        async def event_generator():
            try:
                from transcriber import run_transcription
                loop = asyncio.get_running_loop()
                queue = asyncio.Queue()
                _SENTINEL = object()
                
                def _run_transcribe():
                    try:
                        for chunk in run_transcription(
                            temp_file_path,
                            srt_path,
                            yield_progress=True,
                            language=language,
                            model_size=model_size
                        ):
                            loop.call_soon_threadsafe(queue.put_nowait, chunk)
                    except Exception as exc:
                        loop.call_soon_threadsafe(queue.put_nowait, exc)
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)
                
                loop.run_in_executor(_stream_executor, _run_transcribe)
                
                while True:
                    item = await queue.get()
                    if item is _SENTINEL:
                        break
                    if isinstance(item, Exception):
                        yield json.dumps({"status": "error", "message": str(item)}) + "\n"
                        break
                    yield item
                    
            except Exception as e:
                yield json.dumps({"status": "error", "message": f"转录执行出错: {e}"}) + "\n"
                
            finally:
                # 3. 完美清理临时上传的文件
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                except Exception:
                    pass
                try:
                    if os.path.exists(srt_path):
                        os.remove(srt_path)
                except Exception:
                    pass
                    
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"上传文件处理失败: {e}")
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe_path")
async def api_transcribe_path(request: TranscribePathRequest):
    """
    处理本地视频路径转录的流式端点 (AI Worker)
    """
    media_path = request.path
    language = request.language
    model_size = request.model_size
    
    logger.info(f"🎤 AI Worker 收到本地路径转录请求: path={media_path}, language={language}, model_size={model_size}")
    
    if not os.path.exists(media_path):
        raise HTTPException(status_code=400, detail=f"文件不存在: {media_path}")
        
    srt_path = os.path.splitext(media_path)[0] + "_qwen3.srt"
    
    async def event_generator():
        try:
            from transcriber import run_transcription
            loop = asyncio.get_running_loop()
            queue = asyncio.Queue()
            _SENTINEL = object()
            
            def _run_transcribe():
                try:
                    for chunk in run_transcription(
                        media_path,
                        srt_path,
                        yield_progress=True,
                        language=language,
                        model_size=model_size
                    ):
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, exc)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)
            
            loop.run_in_executor(_stream_executor, _run_transcribe)
            
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    yield json.dumps({"status": "error", "message": str(item)}) + "\n"
                    break
                yield item
                
        except Exception as e:
            yield json.dumps({"status": "error", "message": f"转录执行出错: {e}"}) + "\n"
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

# ========== 上下文截断 ==========

def estimate_tokens(text: str) -> int:
    """粗估 token 数：中文约 1 字 ≈ 1.5 token，英文约 4 字符 ≈ 1 token"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)


def count_message_tokens(messages: list) -> int:
    """估算消息列表的总 token 数"""
    total = 0
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # 多模态消息
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    total += estimate_tokens(part.get('text', ''))
                elif isinstance(part, dict) and part.get('type') == 'image':
                    total += 768  # 图片粗估
        total += 4  # role 开销
    return total


def trim_messages(messages: list, max_tokens: int = None) -> tuple:
    """从顶部截断旧对话，始终保留 system 消息和最近对话。
    
    返回 (trimmed_messages, original_tokens, trimmed_tokens, trimmed_count)
    """
    if max_tokens is None:
        max_tokens = config.get('chat.context_max_tokens', 24576)
    original_tokens = count_message_tokens(messages)
    
    if original_tokens <= max_tokens:
        return messages, original_tokens, original_tokens, 0
    
    # 分离 system 消息和对话消息
    system_msgs = [m for m in messages if m.get('role') == 'system']
    chat_msgs = [m for m in messages if m.get('role') != 'system']
    
    # 从尾部开始保留，直到 token 超限
    kept = []
    token_count = count_message_tokens(system_msgs)  # system 始终算在内
    trimmed_count = 0
    
    for msg in reversed(chat_msgs):
        msg_tokens = 4  # role 开销
        content = msg.get('content', '')
        if isinstance(content, str):
            msg_tokens += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    msg_tokens += estimate_tokens(part.get('text', ''))
                elif isinstance(part, dict) and part.get('type') == 'image':
                    msg_tokens += 768
        
        if token_count + msg_tokens > max_tokens:
            trimmed_count += 1
            continue
        token_count += msg_tokens
        kept.insert(0, msg)
    
    # 正常情况下最后一条应为 user 消息(用户刚发的)
    # 如果不是(异常情况), 不截断, 保留全部对话
    if kept and kept[-1].get('role') != 'user':
        logger.warning("⚠️ 上下文截断: 最后一条非 user 消息, 跳过截断")
        return messages, original_tokens, original_tokens, 0
    
    result = system_msgs + kept
    trimmed_tokens = count_message_tokens(result)
    
    logger.info(f"✂️ 上下文截断: {original_tokens}→{trimmed_tokens} tokens, 截断 {trimmed_count} 条旧消息")
    return result, original_tokens, trimmed_tokens, trimmed_count


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

    # 1. 上下文截断
    messages, orig_tokens, trimmed_tokens, trimmed_count = trim_messages(request.messages)
    
    # 2. 处理联网搜索
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

            # --- 优化:Query 预处理 (关键词提取) ---
            # 只有当显式开启了优化且提问较长时才执行
            if request.optimize_search is True and len(query_text) > 10:
                logger.info(f"🧠 正在为提问进行 AI 关键词优化: '{query_text[:30]}...'")
                try:
                    # 使用更严格的 Prompt
                    # default_optimizer_prompt = f"请将以下问题提炼为 3 个最关键的搜索关键词,用空格隔开。要求:严禁使用序号,严禁换行,直接输出关键词。\n\n问题:{query_text}"
                    default_optimizer_prompt = f"这是用户发来的请求, 先提取里面具体查询的内容, 然后这部分内容提炼为几个最关键的搜索关键词,用空格隔开。要求:严禁使用序号,严禁换行,直接输出关键词。\n\n问题:{query_text}"
                    keyword_prompt = request.search_optimize_prompt.replace("{query}", query_text) if request.search_optimize_prompt else default_optimizer_prompt

                    logger.debug(f"📝 优化 Prompt: {keyword_prompt}")
                    # 使用当前活动的模型生成 (限制最大 100 token 以免关键词生成失控)
                    keywords = summarizer.chat([{"role": "user", "content": keyword_prompt}], max_new_tokens=100).strip()

                    # 强力清洗
                    keywords = keywords.replace("\n", " ").replace("\r", " ")
                    import re
                    keywords = re.sub(r'^\d+[\.、\s:-]+', '', keywords)
                    for prefix in ["关键词:", "关键词:", "Keywords:", "搜索词:", "Search:"]:
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
                # 在最后一条用户消息之前插入 system 消息，不修改用户原始消息
                # 这样多轮对话中用户原始提问不会丢失
                search_system_msg = {
                    "role": "system",
                    "content": f"""【实时联网搜索到的事实资料】
{search_context}

【回答要求】
1. 必须严格按照上述"事实资料"回答。
2. 如果资料中没提到的信息，不要脑补。"""
                }
                last_user_idx = len(messages) - 1 - messages[::-1].index(last_user_msg)
                messages.insert(last_user_idx, search_system_msg)
                logger.info(f"🚀 联网搜索上下文已注入为 system 消息 (长度: {len(search_system_msg['content'])})")

    async def generate():
        # 发送 token 用量信息
        ctx_max = config.get('chat.context_max_tokens', 24576)
        yield f"data: {json.dumps({'type': 'context', 'original_tokens': orig_tokens, 'trimmed_tokens': trimmed_tokens, 'trimmed_count': trimmed_count, 'max_tokens': ctx_max}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)

        # 如果有搜索结果,先发送搜索状态
        if search_context:
            yield f"data: {json.dumps({'type': 'search', 'status': 'done'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)

        try:
            # 关键修复：将同步阻塞的生成器放入线程池，通过 asyncio.Queue 零延迟桥接到异步生成器
            async_queue = asyncio.Queue()
            _SENTINEL = object()
            loop = asyncio.get_running_loop()

            def _run_sync_stream():
                try:
                    for token in summarizer.chat_stream(messages, enable_think=request.enable_think):
                        loop.call_soon_threadsafe(async_queue.put_nowait, token)
                except Exception as e:
                    loop.call_soon_threadsafe(async_queue.put_nowait, e)
                finally:
                    loop.call_soon_threadsafe(async_queue.put_nowait, _SENTINEL)

            loop.run_in_executor(_stream_executor, _run_sync_stream)

            while True:
                token = await async_queue.get()
                if token is _SENTINEL:
                    break
                if isinstance(token, Exception):
                    yield f"data: {json.dumps({'token': f'❌ 生成错误: {token}'}, ensure_ascii=False)}\n\n"
                    break
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

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

def chunk_text(text, max_chunk_size=3000):
    """将长文本按段落拆分为块,每块不超过 max_chunk_size 字符

    拆分策略:
    1. 优先按双换行(段落边界)拆分
    2. 单段落过长时按句号/问号/感叹号(句子边界)拆分
    3. 单句超长时按 max_chunk_size 硬切

    适用于所有提示词类型(翻译、总结、润色等),通用分块函数。
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

    # 处理超长段落:按句子边界拆分
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chunk_size:
            final_chunks.append(chunk)
        else:
            sentences = re.split(r'(?<=[。!?.!?])\s*', chunk)
            sub_chunk = ""
            for sent in sentences:
                if sub_chunk and len(sub_chunk) + len(sent) + 1 > max_chunk_size:
                    final_chunks.append(sub_chunk)
                    sub_chunk = sent
                else:
                    sub_chunk = (sub_chunk + ' ' + sent) if sub_chunk else sent
            if sub_chunk:
                final_chunks.append(sub_chunk)

    # 极端情况:单句超长,硬切
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
        f"你是一个专业的翻译专家。请将以下内容翻译成流畅的{target},"
        f"要求在保留原意的基础上,使其更符合{target}的表达习惯。"
        f"如果是技术内容,请确保专业术语翻译准确。"
        f"只需输出翻译后的内容,不要添加任何解释、注释或前后说明。"
    )


# 各提示词类型的默认参数配置(可在 config.yaml 的 prompts 中用 max_new_tokens 覆盖)
PROMPT_DEFAULTS = {
    'translate':     {'max_new_tokens': 4096},  # 翻译输出长度 ≈ 输入长度
    'summarize':     {'max_new_tokens': 2048},  # 总结输出比原文短
    'action_items':  {'max_new_tokens': 1024},  # 待办列表很短
    'polish':        {'max_new_tokens': 4096},  # 润色后长度 ≈ 原文
    'summarizeHtml': {'max_new_tokens': 4096},  # HTML 输出可能较长
}

# 动作名称映射(用于进度提示文案)
ACTION_NAMES = {
    'translate':     '翻译',
    'summarize':     '总结',
    'action_items':  '待办提取',
    'polish':        '润色',
    'summarizeHtml': '整理',
}


@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    """文本总结接口 - 所有提示词类型统一支持分块流式处理

    通用逻辑:
    1. 长文本(>CHUNK_SIZE)自动按段落/句子拆分为多块
    2. 每块独立流式生成,前端实时渲染
    3. 思考过程(<think>标签)在生成中展开、完成后折叠
    4. 不同提示词类型可配置 max_new_tokens
    """
    prompt_type = request.prompt_type or 'summarize'
    text = request.text
    logger.info(f"📝 收到总结请求: type={prompt_type}, 长度={len(text)}, target_lang={request.target_lang}")

    # ========== 获取系统提示词 ==========
    if prompt_type == 'translate':
        # 翻译模式:动态生成提示词(含目标语言)
        target_lang = request.target_lang or 'zh'
        system_prompt = get_translate_prompt(target_lang)
        prompt_name = f"翻译 → {LANG_MAP.get(target_lang, '中文')}"
    else:
        # 其他模式:从配置读取
        prompts = config.get('prompts', {})
        prompt_info = prompts.get(prompt_type, prompts.get('summarize', {}))
        system_prompt = prompt_info.get('content', "你是一个专业的AI助手。")
        prompt_name = prompt_info.get('name', 'AI')

    # ========== 读取该类型的参数配置 ==========
    type_defaults = PROMPT_DEFAULTS.get(prompt_type, {'max_new_tokens': 2048})
    max_new_tokens = type_defaults.get('max_new_tokens', 2048)

    # 配置文件中可覆盖默认值(prompts.xxx.max_new_tokens)
    prompts_cfg = config.get('prompts', {})
    prompt_cfg = prompts_cfg.get(prompt_type, {})
    if 'max_new_tokens' in prompt_cfg:
        max_new_tokens = prompt_cfg['max_new_tokens']

    # ========== 分块逻辑 ==========
    # 优先使用 request.chunk_size，其次从 config.yaml 读取 summarization.chunk_size, 默认值为 3000
    if request.chunk_size is not None:
        CHUNK_SIZE = request.chunk_size
    else:
        CHUNK_SIZE = config.get('summarization', {}).get('chunk_size', 3000)
    needs_chunking = len(text) > CHUNK_SIZE
    chunks = chunk_text(text, CHUNK_SIZE) if needs_chunking else [text]
    total_chunks = len(chunks)

    action = ACTION_NAMES.get(prompt_type, '处理')
    logger.info(f"📌 {prompt_name}: 分块={needs_chunking}({total_chunks}块), max_tokens={max_new_tokens}")

    # ========== 统一分块流式生成 ==========
    async def generate_chunked():
        full_result = ""

        # 检测是否为本地原生模型，若是且开启了并发，强制优雅退化并发送提示
        is_local_model = not getattr(summarizer, "is_remote", False)
        actual_parallel = request.parallel
        if actual_parallel and is_local_model:
            logger.info("⚠️ 检测到当前为本地原生模型，不支持并行总结，已自动优雅降级为串行模式。")
            actual_parallel = False
            yield json.dumps({"status": "processing", "message": "💡 提示：本地加载模型暂不支持并发加速，已自动转换为安全串行模式以防止 GPU 显存溢出..."}) + "\n"
            await asyncio.sleep(1.0)

        if actual_parallel:
            yield json.dumps({"status": "processing", "message": f"⚡ 正在启动多路并行加速总结（并发数: {total_chunks} 组）..."}) + "\n"
            await asyncio.sleep(0.01)
            
            queues = [asyncio.Queue() for _ in range(total_chunks)]
            _SENTINEL = object()
            loop = asyncio.get_running_loop()
            
            def run_chunk_inference(idx, chunk_msg, queue):
                try:
                    chunk_res = ""
                    for token in summarizer.chat_stream(chunk_msg, max_new_tokens=max_new_tokens):
                        chunk_res += token
                        loop.call_soon_threadsafe(queue.put_nowait, {"type": "streaming", "delta": token})
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "chunk_complete", "result": chunk_res})
                except Exception as e:
                    logger.error(f"{action}第 {idx+1} 段并发推理失败: {e}")
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": f"{action}第 {idx+1}/{total_chunks} 段并发处理失败: {str(e)}"})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)

            # 1. 并发派发所有分块的线程任务到线程池
            for i, chunk in enumerate(chunks):
                if prompt_type == 'translate':
                    user_content = chunk
                else:
                    user_content = f"以下是需要处理的文本内容:\n\n{chunk}"

                chunk_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
                
                # 并发执行
                loop.run_in_executor(_stream_executor, run_chunk_inference, i, chunk_messages, queues[i])

            # 2. 按顺序从各个队列中读取并流式发送，保证前端 100% 物理顺序和流式渲染兼容
            for i in range(total_chunks):
                queue = queues[i]
                chunk_result = ""
                
                # 发送分块开始进度
                yield json.dumps({
                    "status": "processing",
                    "message": f"正在并发流式输出第 {i+1}/{total_chunks} 段...",
                    "chunk": i + 1,
                    "total_chunks": total_chunks
                }) + "\n"
                await asyncio.sleep(0.01)
                
                while True:
                    msg = await queue.get()
                    if msg is _SENTINEL:
                        break
                    if msg["type"] == "error":
                        yield json.dumps({"status": "error", "message": msg["message"]}) + "\n"
                        return
                    elif msg["type"] == "streaming":
                        token = msg["delta"]
                        chunk_result += token
                        full_result += token
                        yield json.dumps({"status": "streaming", "delta": token}) + "\n"
                        await asyncio.sleep(0)
                    elif msg["type"] == "chunk_complete":
                        yield json.dumps({"status": "chunk_complete", "chunk": i + 1, "total_chunks": total_chunks, "chunk_result": chunk_result}) + "\n"
                
                # 块之间添加换行
                if i < total_chunks - 1:
                    full_result += "\n\n"
        else:
            # 串行流式处理
            for i, chunk in enumerate(chunks):
                # 发送分块进度
                if needs_chunking:
                    yield json.dumps({
                        "status": "processing",
                        "message": f"正在{action}第 {i+1}/{total_chunks} 段...",
                        "chunk": i + 1,
                        "total_chunks": total_chunks
                    }) + "\n"
                else:
                    yield json.dumps({"status": "processing", "message": f"正在{action}..."}) + "\n"
                await asyncio.sleep(0.01)

                if prompt_type == 'translate':
                    user_content = chunk
                else:
                    user_content = f"以下是需要处理的文本内容:\n\n{chunk}"

                chunk_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]

                try:
                    chunk_result = ""
                    for token in summarizer.chat_stream(chunk_messages, max_new_tokens=max_new_tokens):
                        chunk_result += token
                        full_result += token
                        yield json.dumps({"status": "streaming", "delta": token}) + "\n"
                        await asyncio.sleep(0)

                    yield json.dumps({"status": "chunk_complete", "chunk": i + 1, "total_chunks": total_chunks, "chunk_result": chunk_result}) + "\n"

                    if i < total_chunks - 1:
                        full_result += "\n\n"
                except Exception as e:
                    logger.error(f"{action}第 {i+1} 段失败: {e}")
                    yield json.dumps({"status": "error", "message": f"{action}第 {i+1}/{total_chunks} 段失败: {str(e)}"}) + "\n"
                    break

        yield json.dumps({"status": "done", "result": full_result}) + "\n"

        # 清理 GPU 缓存
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

    return StreamingResponse(
        generate_chunked(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
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
    # 0. 调试信息:打印远程请求内容
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
                for token in summarizer.chat_stream(request.messages, max_new_tokens=request.max_tokens):
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
        response_text = summarizer.chat(request.messages, max_new_tokens=request.max_tokens)
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
    import uvicorn as _uv
    log_cfg = _uv.config.LOGGING_CONFIG.copy()
    log_cfg["formatters"]["default"]["()"] = "uvicorn.logging.DefaultFormatter"
    log_cfg["formatters"]["default"]["use_colors"] = False
    log_cfg["formatters"]["access"]["()"] = "uvicorn.logging.AccessFormatter"
    log_cfg["formatters"]["access"]["use_colors"] = False
    _uv.run(app, host="0.0.0.0", port=8001, log_config=log_cfg)

