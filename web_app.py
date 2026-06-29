"""
web_app.py - 主 Web 服务（无 CUDA 依赖）

端口 8000，处理：
- 静态页面、TTS、GPU 监控、文件下载
- AI 请求代理到 ai_worker（端口 8001）

架构：
┌──────────────────────┐     ┌──────────────────────┐
│  web_app.py (8000)  │     │  ai_worker.py (8001)  │
│  FastAPI + TTS        │ ←→ │  torch + AI模型       │
│  GPU监控（pynvml）     │     │  chat / summarize     │
│  不导入 torch          │     │  transcribe          │
│  显存 ≈ 0             │     │  显存 ≈ 2.5GB        │
└──────────────────────┘     └──────────────────────┘
                                      ↓ 释放显存
                               kill 子进程 → 显存归 0 ✅
"""

import os
import sys
import re
from datetime import datetime
# 确保项目根目录在路径中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import signal
import subprocess
import threading
import time
import json
import psutil
import atexit
import asyncio
import httpx

# 存储正在运行的子进程：{ "task_name": process_object }
running_processes = {}
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

import pynvml
import logging
from tts_engine import TTSEngine
from config_loader import config

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.get('logging.level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.get('logging.file', 'logs/app.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 过滤 httpx 模块的 INFO 级别日志以避免轮询产生的请求刷屏
logging.getLogger("httpx").setLevel(logging.WARNING)

# 过滤 uvicorn.access 日志中轮询请求的噪音
class SkipPollingFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        for skip_path in ['/api/worker_status', '/api/gpu_stats', '/api/ollama_status', '/health']:
            if skip_path in msg:
                return False
        return True

# 应用到 uvicorn.access logger
for logger_name in ['uvicorn.access', 'uvicorn.error']:
    logging.getLogger(logger_name).addFilter(SkipPollingFilter())

# ========== 配置 ==========

AI_WORKER_PORT = 8001
AI_WORKER_HOST = "127.0.0.1"
AI_WORKER_URL = f"http://{AI_WORKER_HOST}:{AI_WORKER_PORT}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

app = FastAPI(title="Qwen3 ASR Web Console")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 状态标志：服务是否正在关闭
is_shutting_down = False
original_sigint_handler = None
original_sigterm_handler = None

def graceful_signal_handler(signum, frame):
    global is_shutting_down
    if not is_shutting_down:
        is_shutting_down = True
        logger.info("💥 捕获到终止信号 (SIGINT/SIGTERM)，正在主动释放所有后台长连接...")
    
    # 链式调用原来的信号处理器，让 uvicorn 正常收尾
    handler = original_sigint_handler if signum == 2 else original_sigterm_handler  # 2 表示 signal.SIGINT
    if handler and callable(handler):
        handler(signum, frame)

@app.on_event("startup")
async def startup_event():
    global original_sigint_handler, original_sigterm_handler
    import signal
    
    try:
        # 包装 SIGINT (Ctrl+C)
        sigint_handler = signal.getsignal(signal.SIGINT)
        if sigint_handler != graceful_signal_handler:
            original_sigint_handler = sigint_handler
            signal.signal(signal.SIGINT, graceful_signal_handler)
            logger.info("已成功包装 Uvicorn 的 SIGINT 信号处理器，实现长连接秒级优雅退出")
    except Exception as e:
        logger.debug(f"包装 SIGINT 信号处理器失败: {e}")

    try:
        # 包装 SIGTERM (系统终止)
        sigterm_handler = signal.getsignal(signal.SIGTERM)
        if sigterm_handler != graceful_signal_handler:
            original_sigterm_handler = sigterm_handler
            signal.signal(signal.SIGTERM, graceful_signal_handler)
            logger.info("已成功包装 Uvicorn 的 SIGTERM 信号处理器，实现长连接秒级优雅退出")
    except Exception as e:
        logger.debug(f"包装 SIGTERM 信号处理器失败: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global is_shutting_down
    is_shutting_down = True
    ai_worker.intentional_stop = True
    logger.info("主服务正在关闭，通知所有后台长连接释放...")
    try:
        await http_client.aclose()
        logger.info("✓ 全局 HTTP 客户端连接池已成功关闭并释放资源")
    except Exception as e:
        logger.warning(f"关闭全局 HTTP 客户端连接池时出错: {e}")

# ========== 初始化 ==========

pynvml.nvmlInit()
tts_engine = TTSEngine()

# 全局可复用的异步 HTTP 客户端连接池，配置大容量 keepalive
# 消除系统后台高频轮询（GPU状态、Ollama存活等）导致的 Socket 端口重建开销与 TIME_WAIT 积压
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=200),
    timeout=httpx.Timeout(300.0),  # 对应大文件或长文 AI 响应 the default timeout
    trust_env=False  # 核心修复：强制忽略本地代理，防止本地 Clash / v2rayN 劫持本地 127.0.0.1:8001 导致 500
)

# ========== AI Worker 进程管理 ==========

class AIWorkerManager:
    """管理 AI Worker 子进程的生命周期，支持侧车意外中断自动拉起（Auto-Respawn）"""
    
    def __init__(self):
        self.process = None
        self._start_time = 0
        self.intentional_stop = False
        self.respawn_count = 0
        self.max_respawn = 3
        self.is_respawning = False
        self.respawn_message = ""
        atexit.register(self.kill)
    
    def is_running(self) -> bool:
        """检查 worker 是否运行中"""
        if self.process is None:
            return False
        retcode = self.process.poll()
        if retcode is not None:
            # 进程已退出，记录退出码
            if not self.intentional_stop and not is_shutting_down:
                logger.warning(f"AI Worker 进程意外退出，退出码: {retcode}")
            else:
                logger.info(f"AI Worker 进程退出，退出码: {retcode}")
            # 尝试读取子进程的输出（错误信息）
            try:
                output = self.process.stdout.read() if self.process.stdout else ''
                if output:
                    logger.warning(f"AI Worker 最后输出: {output[-500:]}")
            except:
                pass
            self.process = None
            return False
        return True
    
    def start(self) -> dict:
        """启动 AI Worker 子进程"""
        if self.is_running():
            return {"status": "already_running", "message": "AI Worker 已在运行"}
        
        self.intentional_stop = False
        logger.info("启动 AI Worker 子进程...")
        
        # 使用当前 Python 解释器
        python_exe = sys.executable
        worker_script = os.path.join(BASE_DIR, "ai_worker.py")
        
        self.process = subprocess.Popen(
            [python_exe, worker_script, "--port", str(AI_WORKER_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        self._start_time = time.time()
        
        # 启动后台线程持续读取子进程输出，防止管道阻塞，并充当侧车守护线程
        import threading
        def _read_worker_output(proc):
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    # 跳过 AI Worker 的 uvicorn access 日志（健康检查）
                    if '/health' in line or '"GET' in line and '200 OK' in line:
                        continue
                    logger.info(f"[Worker] {line}")
            except:
                pass
            
            # 当输出管道关闭（子进程结束时），进行守护拉起检测
            time.sleep(0.5)  # 稍微等待防抖以获取真实退出码
            retcode = proc.poll()
            
            # 只有当非人为主动停止，且主服务未关机，且进程确实退出时，才触发自动守护
            if not self.intentional_stop and not is_shutting_down and retcode is not None:
                logger.warning(f"💥 AI Worker 进程异常退出，退出码: {retcode}")
                # 只有当当前活跃进程仍然是此 proc 时，才置空并触发自动拉起，避免并发冲突
                if self.process == proc:
                    self.process = None
                    
                    if self.respawn_count < self.max_respawn:
                        self.respawn_count += 1
                        self.is_respawning = True
                        self.respawn_message = f"后端 AI 服务异常退出 (代码: {retcode})，正在自动拉起中 ({self.respawn_count}/{self.max_respawn} 次)..."
                        logger.warning(f"🔄 {self.respawn_message}")
                        
                        # 稍微等待 1.5 秒以确保端口与系统资源释放
                        time.sleep(1.5)
                        
                        # 调用启动方法重新拉起
                        start_res = self.start()
                        if start_res.get("status") == "started":
                            logger.info(f"✅ AI Worker 进程自动重新拉起成功！")
                            self.is_respawning = False
                            self.respawn_message = ""
                            self.respawn_count = 0  # 恢复成功后重置计数
                        else:
                            logger.error(f"❌ AI Worker 进程自动拉起失败: {start_res.get('message')}")
                            self.is_respawning = False
                            self.respawn_message = f"自动拉起失败: {start_res.get('message')}"
                    else:
                        logger.error(f"❌ AI Worker 异常退出重试已达上限 ({self.max_respawn}次)，放弃自动拉起。")
                        self.respawn_message = "后端服务持续异常崩溃，已达最大重试上限。请点击侧边栏「释放显存」后重新手动启动。"
        
        t = threading.Thread(target=_read_worker_output, args=(self.process,), daemon=True)
        t.start()
        
        # 等待启动（最多 30 秒）
        logger.info("等待 AI Worker 就绪...")
        for i in range(30):
            time.sleep(1)
            if not self.is_running():
                logger.error("AI Worker 启动失败")
                return {"status": "error", "message": "AI Worker 启动失败"}
            
            # 尝试健康检查
            try:
                import requests
                resp = requests.get(f"{AI_WORKER_URL}/health", timeout=1)
                if resp.status_code == 200:
                    logger.info(f"AI Worker 已就绪 ({i+1}秒)")
                    return {"status": "started", "message": f"AI Worker 启动成功 ({i+1}秒)"}
            except:
                pass
        
        logger.warning("AI Worker 启动超时")
        return {"status": "timeout", "message": "AI Worker 启动超时"}
    
    def kill(self) -> dict:
        """终止 AI Worker 子进程（完全释放显存）"""
        logger.info("终止 AI Worker 子进程...")
        self.intentional_stop = True
        self.respawn_count = 0  # 释放时重置所有重试状态
        self.is_respawning = False
        self.respawn_message = ""
        
        if self.process is None:
            return {"status": "not_running", "message": "AI Worker 未运行"}
        
        if not self.is_running():
            self.process = None
            return {"status": "already_stopped", "message": "AI Worker 已停止"}
        
        # Windows: 使用 terminate() 或 taskkill
        self.process.terminate()
        
        # 等待进程退出（最多 5 秒）
        try:
            self.process.wait(timeout=5)
            logger.info("AI Worker 已正常终止")
        except subprocess.TimeoutExpired:
            # 强制杀死
            self.process.kill()
            logger.warning("AI Worker 已强制终止")
        
        self.process = None
        
        # 确认 GPU 显存已释放（给系统一点时间）
        time.sleep(0.5)
        
        return {"status": "killed", "message": "AI Worker 已终止，显存已释放"}
    
    def ensure_running(self) -> bool:
        """确保 worker 运行，如果没运行则启动"""
        if self.is_running():
            return True
        
        # 如果正在自动重新拉起中，直接返回 False 避免并发干扰
        if self.is_respawning:
            return False
            
        result = self.start()
        return result["status"] in ["started", "already_running"]
    
    def get_status(self) -> dict:
        """获取 worker 状态"""
        running = self.is_running()
        uptime = time.time() - self._start_time if running and self._start_time > 0 else 0
        return {
            "running": running,
            "uptime_seconds": int(uptime),
            "url": AI_WORKER_URL if running else None,
            "respawning": self.is_respawning,
            "respawn_message": self.respawn_message
        }

ai_worker = AIWorkerManager()

# ========== 代理工具函数 ==========

async def proxy_to_worker(method: str, path: str, **kwargs):
    """代理请求到 AI Worker (复用全局 HTTP 连接池)"""
    # 确保 worker 已启动，如果未启动则返回错误
    if not ai_worker.ensure_running():
        return {"error": "AI Worker 启动失败"}
    url = f"{AI_WORKER_URL}{path}"
    resp = await http_client.request(method, url, **kwargs)
    return resp.json()

async def proxy_stream_to_worker(method: str, path: str, **kwargs):
    """代理流式请求到 AI Worker (复用全局 HTTP 连接池)"""
    # 确保 worker 已启动，如果未启动则返回错误并自动托起
    if not ai_worker.ensure_running():
        async def error_gen():
            yield (json.dumps({"status": "error", "message": "AI Worker 启动失败"}) + "\n").encode("utf-8")
        return StreamingResponse(
            error_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    
    url = f"{AI_WORKER_URL}{path}"
    
    try:
        # 使用全局连接池发起流式请求，确保流结束后仅释放 response 资源，而非整个 client 资源
        if method.upper() == "GET":
            req = http_client.build_request("GET", url, **kwargs)
        else:
            req = http_client.build_request("POST", url, **kwargs)
            
        resp = await http_client.send(req, stream=True)
        
        async def stream_gen():
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                
        return StreamingResponse(
            stream_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    except Exception as e:
        async def error_gen():
            yield (json.dumps({"status": "error", "message": f"代理流式请求失败: {e}"}) + "\n").encode("utf-8")
        return StreamingResponse(
            error_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

# ========== Pydantic 模型 ==========

class ChatRequest(BaseModel):
    messages: list
    model_id: str = None  # 可选：指定模型
    enable_search: bool = True  # 是否启用联网搜索（默认开启）
    optimize_search: bool = True  # 是否启用关键词优化（默认开启）
    enable_think: bool = True  # 是否启用深度思考（默认开启）
    search_optimize_prompt: str = None  # 自定义优化提示词

class SummarizeRequest(BaseModel):
    text: str
    prompt_type: Optional[str] = "summarize"
    target_lang: Optional[str] = None  # 目标语言，仅用于翻译模式
    parallel: Optional[bool] = False
    chunk_size: Optional[int] = None

class DigestRequest(BaseModel):
    session_id: int
    date: Optional[str] = None

class SwitchModelRequest(BaseModel):
    model_id: str

class SaveChatRequest(BaseModel):
    title: str
    messages: list
    path: Optional[str] = None

# ========== 对话历史存储逻辑 ==========

CHATS_DIR = os.path.join(BASE_DIR, "chats")
os.makedirs(CHATS_DIR, exist_ok=True)

@app.post("/api/history/save")
async def save_history(request: SaveChatRequest):
    """保存对话到本地磁盘"""
    try:
        from datetime import datetime
        
        # 覆盖写逻辑：若指定了已有文件路径，则覆盖更新，避免多余文件产生
        if request.path:
            safe_path = os.path.normpath(request.path).lstrip(os.sep + "/")
            filepath = os.path.join(CHATS_DIR, safe_path)
            if filepath.startswith(CHATS_DIR) and os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "title": request.title,
                        "timestamp": datetime.now().isoformat(),
                        "messages": request.messages
                    }, f, ensure_ascii=False, indent=2)
                return {"status": "success", "path": safe_path.replace(os.sep, "/")}

        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H-%M-%S")
        
        date_dir = os.path.join(CHATS_DIR, today)
        os.makedirs(date_dir, exist_ok=True)
        
        # 文件名只用时间戳，标题存 JSON 内部，避免特殊字符问题
        filename = f"{now_time}.json"
        filepath = os.path.join(date_dir, filename)
        
        # 如果文件已存在（同秒保存），加序号
        counter = 1
        while os.path.exists(filepath):
            filename = f"{now_time}_{counter}.json"
            filepath = os.path.join(date_dir, filename)
            counter += 1
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "title": request.title,
                "timestamp": datetime.now().isoformat(),
                "messages": request.messages
            }, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "path": f"{today}/{filename}".replace(os.sep, "/")}
    except Exception as e:
        logger.error(f"保存对话失败: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/history/list")
async def list_history(limit: int = 50, offset: int = 0, query: str = None):
    """获取对话列表，支持分页和搜索"""
    import glob
    all_files = []
    for file_path in glob.glob(os.path.join(CHATS_DIR, "**", "*.json"), recursive=True):
        mtime = os.path.getmtime(file_path)
        rel_path = os.path.relpath(file_path, CHATS_DIR)
        
        # 从 JSON 文件读取标题（兼容旧格式：标题在文件名中）
        title = None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("title", "")
        except Exception:
            pass
        
        # 旧格式兼容：如果 JSON 中没有标题，从文件名提取
        if not title:
            parts = rel_path.split(os.sep)
            if len(parts) >= 2:
                filename = parts[1]
                title = filename.split("_", 1)[1].rsplit(".", 1)[0] if "_" in filename else filename
            else:
                title = rel_path
        
        # 格式化日期前缀
        parts = rel_path.split(os.sep)
        date_str = parts[0] if len(parts) >= 2 else ""
        display_title = f"[{date_str}] {title}" if date_str else title
        
        all_files.append({
            "path": rel_path.replace(os.sep, "/"),
            "title": display_title,
            "mtime": mtime
        })
    
    # 搜索过滤
    if query:
        query_lower = query.lower()
        all_files = [f for f in all_files if query_lower in f["title"].lower()]
    
    all_files.sort(key=lambda x: x["mtime"], reverse=True)
    total = len(all_files)
    items = all_files[offset:offset + limit]
    return {"total": total, "items": items}

@app.get("/api/history/load")
async def load_history(path: str):
    """读取指定对话内容"""
    try:
        safe_path = os.path.normpath(path).lstrip(os.sep + "/")
        filepath = os.path.join(CHATS_DIR, safe_path)
        if not filepath.startswith(CHATS_DIR) or not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/history/delete")
async def delete_history(path: str):
    """删除指定对话"""
    try:
        safe_path = os.path.normpath(path).lstrip(os.sep + "/")
        filepath = os.path.join(CHATS_DIR, safe_path)
        if not filepath.startswith(CHATS_DIR):
            return {"status": "error", "message": "非法路径"}
        if not os.path.exists(filepath):
            return {"status": "error", "message": "文件不存在"}
        os.remove(filepath)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        return {"status": "error", "message": str(e)}

# ========== 数据分析与资源提取 API ==========

@app.get("/api/analytics/sessions")
async def api_analytics_sessions():
    """获取所有可分析的微信会话列表"""
    try:
        from chat_analytics import ChatAnalytics
        analytics = ChatAnalytics()
        cursor = analytics.conn.cursor()
        cursor.execute("""
            SELECT id, wxid, nickname, remark, message_count 
            FROM sessions 
            ORDER BY message_count DESC
        """)
        rows = cursor.fetchall()
        sessions = []
        for r in rows:
            sessions.append({
                "id": r['id'],
                "wxid": r['wxid'],
                "name": r['remark'] or r['nickname'] or "未知会话",
                "message_count": r['message_count']
            })
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"获取分析会话列表失败: {e}")
        return {"error": str(e)}

@app.get("/api/analytics/resources")
async def api_analytics_resources(
    resource_type: Optional[str] = None,
    session_id: Optional[int] = None,
    search_query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """分页拉取已提取的干货资源列表"""
    try:
        from wechat_db import wechat_db
        res_list = wechat_db.get_extracted_resources(
            session_id=session_id,
            resource_type=resource_type,
            limit=limit,
            offset=offset,
            search_query=search_query
        )
        return {"resources": res_list}
    except Exception as e:
        logger.error(f"拉取资源列表失败: {e}")
        return {"error": str(e)}

@app.get("/api/analytics/topics")
async def api_analytics_topics(
    session_id: int,
    month: Optional[str] = None,
    top: int = 15
):
    """获取群聊词频/主题提取结果"""
    try:
        from chat_analytics import ChatAnalytics
        import jieba.analyse
        from collections import defaultdict
        
        analytics = ChatAnalytics()
        cursor = analytics.conn.cursor()
        query = "SELECT create_time, content FROM messages WHERE session_id = ? AND type IN ('text', '文本消息')"
        params = [session_id]
        if month:
            query += " AND strftime('%Y-%m', datetime(create_time, 'unixepoch')) = ?"
            params.append(month)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            return {"keywords": [], "monthly_trends": {}}
            
        monthly_text = defaultdict(list)
        all_text = []
        for r in rows:
            content = r['content'] or ''
            content = re.sub(r'\[\w+\]', '', content)
            content = re.sub(r'>\s*@.*?\s*\n', '', content)
            
            dt = datetime.fromtimestamp(r['create_time'])
            m_str = dt.strftime("%Y-%m")
            monthly_text[m_str].append(content)
            all_text.append(content)
            
        # 整体热词
        combined_all = " ".join(all_text)
        tags = jieba.analyse.extract_tags(combined_all, topK=top, withWeight=True, allowPOS=('n', 'nr', 'ns', 'nt'))
        keywords = [{"word": w, "weight": wt} for w, wt in tags]
        
        # 月度热词演变
        monthly_trends = {}
        for m in sorted(monthly_text.keys()):
            m_combined = " ".join(monthly_text[m])
            m_tags = jieba.analyse.extract_tags(m_combined, topK=5, allowPOS=('n', 'nr', 'ns', 'nt'))
            monthly_trends[m] = m_tags
            
        return {
            "keywords": keywords,
            "monthly_trends": monthly_trends
        }
    except Exception as e:
        logger.error(f"获取主题分析失败: {e}")
        return {"error": str(e)}

@app.get("/api/analytics/network")
async def api_analytics_network(session_id: int):
    """获取群聊社交网络拓扑数据"""
    try:
        from chat_analytics import ChatAnalytics
        import networkx as nx
        
        analytics = ChatAnalytics()
        cursor = analytics.conn.cursor()
        # 1. 从 group_members 获取本群成员的微信名与群昵称映射（解决@名称与发言微信昵称不一致的问题）
        cursor.execute("""
            SELECT wxid, wechat_name, nickname 
            FROM group_members 
            WHERE session_id = ?
        """, (session_id,))
        member_rows = cursor.fetchall()

        wxid_to_group_name = {}
        wechat_name_to_group_name = {}
        group_names = set()

        for row in member_rows:
            wxid = row[0]
            wechat_name = row[1]
            group_name = row[2]
            
            # 过滤掉默认空字符
            if not group_name or group_name.strip() in ('-', ''):
                group_name = wechat_name if wechat_name and wechat_name.strip() not in ('-', '') else wxid
                
            if group_name:
                wxid_to_group_name[wxid] = group_name
                if wechat_name:
                    wechat_name_to_group_name[wechat_name] = group_name
                # 只保留长度>=2的名称用作正则匹配，避免误触
                if len(group_name) >= 2:
                    group_names.add(group_name)

        # 2. 获取包含 @ 符号的所有消息内容
        cursor.execute("""
            SELECT sender_display_name, content, sender_username 
            FROM messages 
            WHERE session_id = ? AND content LIKE '%@%'
        """, (session_id,))
        rows = cursor.fetchall()
        
        edges = []
        # 构建 @群名片 形式的正则表达式模式
        escaped_members = [re.escape(g) for g in group_names]
        mention_pattern = None
        if escaped_members:
            # 匹配 @群名片 后接空格、艾特空格、冒号、标点或行尾
            mention_pattern = re.compile(r'@(' + '|'.join(escaped_members) + r')(?:\u2005|\s|:|：|[,，。.]|$)')
            
        reply_pattern = re.compile(r'^>\s*@([^\s：:]+)')
        
        for r in rows:
            sender_display = r[0]
            content = r[1] or ''
            sender_wxid = r[2]
            
            # 获取发言人在本群的群名片（展示更直观）
            replier_name = wxid_to_group_name.get(sender_wxid) or wechat_name_to_group_name.get(sender_display) or sender_display or sender_wxid
            if not replier_name:
                continue
                
            # 1. 匹配 @群名片 的互动关系
            if mention_pattern:
                matches = mention_pattern.findall(content)
                for target_group_name in matches:
                    if replier_name != target_group_name:
                        edges.append((replier_name, target_group_name))
            
            # 2. 备用匹配引用模式 ('> @昵称') 并尝试转换为本群名片
            match = reply_pattern.match(content)
            if match:
                target_display = match.group(1)
                # 寻找对应的群名片
                target_group_name = wechat_name_to_group_name.get(target_display) or target_display
                if replier_name != target_group_name:
                    edges.append((replier_name, target_group_name))
                    
        # 查询本群活跃度（发言最多）的前10名家长名片，供排行榜展示
        cursor.execute("""
            SELECT sender_username, sender_display_name, COUNT(*) as cnt 
            FROM messages 
            WHERE session_id = ? AND sender_username IS NOT NULL AND sender_username != ''
            GROUP BY sender_username 
            ORDER BY cnt DESC 
            LIMIT 10
        """, (session_id,))
        active_counts = cursor.fetchall()
        
        active_speakers = []
        for r in active_counts:
            wxid = r[0]
            display = r[1]
            cnt = r[2]
            group_name = wxid_to_group_name.get(wxid) or wechat_name_to_group_name.get(display) or display or wxid
            active_speakers.append({"name": group_name, "count": cnt})

        if not edges:
            return {
                "nodes": [], 
                "links": [], 
                "influence": [], 
                "bridges": [], 
                "active_speakers": active_speakers
            }
            
        G = nx.DiGraph()
        for u, v in edges:
            if G.has_edge(u, v):
                G[u][v]['weight'] += 1
            else:
                G.add_edge(u, v, weight=1)
                
        # 计算指标
        in_degree = nx.in_degree_centrality(G)
        betweenness = nx.betweenness_centrality(G)
        
        # 格式化关系图
        nodes_data = []
        for node in G.nodes():
            deg = G.degree(node)
            nodes_data.append({
                "name": node,
                "symbolSize": max(12, min(deg * 2.5, 70)),
                "value": deg
            })
            
        links_data = []
        for u, v, d in G.edges(data=True):
            links_data.append({
                "source": u,
                "target": v,
                "weight": d['weight']
            })
            
        # 排行榜
        sorted_influence = [{"name": name, "score": round(score, 4)} for name, score in sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]]
        sorted_bridges = [{"name": name, "score": round(score, 4)} for name, score in sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]]
        
        return {
            "nodes": nodes_data,
            "links": links_data,
            "influence": sorted_influence,
            "bridges": sorted_bridges,
            "active_speakers": active_speakers
        }
    except Exception as e:
        logger.error(f"构建社交网络图谱失败: {e}")
        return {"error": str(e)}

# ========== 页面端点 ==========

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"config": config})

@app.get("/wechat_console", response_class=HTMLResponse)
async def get_wechat_console(request: Request):
    return templates.TemplateResponse(request=request, name="wechat_console.html", context={"config": config})

# ========== 文档浏览端点 ==========

# 允许浏览的目录（相对于 BASE_DIR）
DOCS_SCAN_DIRS = ["", "docs", "templates"]  # 空字符串表示根目录
# 排除的目录名
DOCS_EXCLUDE_DIRS = {"venv", "models", "scratch", "__pycache__", ".git", "node_modules", "gptqmodel_build"}

# 文件列表缓存（5 秒 TTL）
_docs_cache = {"ts": 0.0, "data": None}

@app.get("/api/docs/list")
async def api_docs_list():
    """列出项目目录下的 HTML 和 Markdown 文件（带 5 秒 TTL 缓存）"""
    global _docs_cache
    now = time.time()
    if _docs_cache["data"] is not None and (now - _docs_cache["ts"]) < 5:
        return {"files": _docs_cache["data"], "cached": True}

    files = []
    seen = set()  # 去重（按相对路径）
    
    for scan_dir in DOCS_SCAN_DIRS:
        search_root = os.path.join(BASE_DIR, scan_dir)
        if not os.path.isdir(search_root):
            continue
        
        for dirpath, dirnames, filenames in os.walk(search_root):
            # 排除目录（原地修改 dirnames 以跳过）
            dirnames[:] = [d for d in dirnames if d not in DOCS_EXCLUDE_DIRS]
            
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in ('.html', '.htm', '.md'):
                    continue
                
                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
                
                if rel_path in seen:
                    continue
                seen.add(rel_path)
                
                try:
                    stat = os.stat(full_path)
                    files.append({
                        "name": fname,
                        "path": rel_path,
                        "type": "html" if ext in ('.html', '.htm') else "markdown",
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except OSError:
                    continue
    
    # 按修改时间倒序
    files.sort(key=lambda f: f["modified"], reverse=True)
    
    # 格式化 modified 为可读字符串
    for f in files:
        from datetime import datetime
        ts = f["modified"]
        f["modified_str"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        # 人类可读的文件大小
        size = f["size"]
        if size < 1024:
            f["size_str"] = f"{size} B"
        elif size < 1024 * 1024:
            f["size_str"] = f"{size/1024:.1f} KB"
        else:
            f["size_str"] = f"{size/1024/1024:.1f} MB"
    
    _docs_cache = {"ts": now, "data": files}
    return {"files": files}


@app.get("/api/docs/read")
async def api_docs_read(path: str):
    """读取文档文件内容"""
    # 安全检查：用 realpath 解析所有 .. 和符号链接，防止路径遍历
    raw = os.path.join(BASE_DIR, path.replace("\\", "/"))
    full_path = os.path.realpath(raw)
    base_real = os.path.realpath(BASE_DIR)
    if not (full_path == base_real or full_path.startswith(base_real + os.sep)):
        return {"error": "路径不合法"}
    
    if not os.path.isfile(full_path):
        return {"error": "文件不存在"}
    
    ext = os.path.splitext(full_path)[1].lower()
    if ext not in ('.html', '.htm', '.md'):
        return {"error": "不支持的文件类型"}
    
    try:
        # 尝试 UTF-8，失败则用 GBK
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(full_path, "r", encoding="gbk", errors="replace") as f:
                content = f.read()
        
        return {
            "name": os.path.basename(full_path),
            "path": os.path.relpath(full_path, BASE_DIR).replace("\\", "/"),
            "type": "html" if ext in ('.html', '.htm') else "markdown",
            "content": content,
        }
    except Exception as e:
        return {"error": f"读取失败: {str(e)}"}


@app.get("/api/docs/view")
async def api_docs_view(path: str):
    """在新标签页中全屏查看文档（返回完整 HTML 页面）"""
    # 安全检查：用 realpath 解析所有 .. 和符号链接，防止路径遍历
    raw = os.path.join(BASE_DIR, path.replace("\\", "/"))
    full_path = os.path.realpath(raw)
    base_real = os.path.realpath(BASE_DIR)
    if not (full_path == base_real or full_path.startswith(base_real + os.sep)):
        return HTMLResponse("<h1>路径不合法</h1>", status_code=400)
    
    if not os.path.isfile(full_path):
        return HTMLResponse("<h1>文件不存在</h1>", status_code=404)
    
    # 二次确认扩展名（realpath 解析后再次检查）
    ext = os.path.splitext(full_path)[1].lower()
    if ext not in ('.html', '.htm', '.md'):
        return HTMLResponse("<h1>不支持的文件类型</h1>", status_code=400)
    
    try:
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(full_path, "r", encoding="gbk", errors="replace") as f:
                content = f.read()
        
        filename = os.path.basename(full_path)
        
        if ext in ('.html', '.htm'):
            # HTML 文件：原样返回（注入返回按钮）
            back_btn = '''<div style="position:fixed;top:12px;right:16px;z-index:99999">
                <a href="/" target="_self" style="background:#0ea5e9;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px;font-family:system-ui">← 返回</a>
            </div>'''
            # 在 <body> 开头注入返回按钮
            if "<body" in content:
                content = content.replace("<body", back_btn + "<body", 1)
            else:
                content = back_btn + content
            return HTMLResponse(content)
        
        elif ext == '.md':
            # Markdown 文件：返回带渲染框架的完整 HTML 页面
            html_page = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{filename}</title>
<!-- KaTeX CSS -->
<link rel="stylesheet" href="/static/css/katex.min.css">
<!-- marked.js -->
<script src="/static/js/marked.min.js"></script>
<!-- Mermaid -->
<script src="/static/js/mermaid.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0;
    line-height: 1.7;
    padding: 20px 40px;
    max-width: 1000px;
    margin: 0 auto;
}}
#back-btn {{
    position: fixed; top: 12px; right: 16px; z-index: 99999;
    background: #0ea5e9; color: #fff; padding: 6px 14px; border-radius: 6px;
    text-decoration: none; font-size: 13px; font-family: system-ui;
}}
#back-btn:hover {{ background: #0284c7; }}
#content {{ margin-top: 10px; }}
#content h1 {{ font-size: 2em; margin: 0.5em 0 0.3em; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.3em; }}
#content h2 {{ font-size: 1.5em; margin: 0.6em 0 0.25em; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 0.2em; }}
#content h3 {{ font-size: 1.25em; margin: 0.7em 0 0.2em; }}
#content p {{ margin: 0.6em 0; }}
#content code {{ background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
#content pre {{ background: rgba(0,0,0,0.35); border-radius: 8px; padding: 16px; overflow-x: auto; margin: 0.8em 0; }}
#content pre code {{ background: none; padding: 0; font-size: 0.85em; line-height: 1.55; }}
#content blockquote {{ border-left: 3px solid #0ea5e9; margin: 0.8em 0; padding: 0.4em 1em; color: rgba(255,255,255,0.6); }}
#content table {{ border-collapse: collapse; width: 100%; margin: 0.8em 0; }}
#content th, #content td {{ border: 1px solid rgba(255,255,255,0.12); padding: 8px 12px; text-align: left; }}
#content th {{ background: rgba(255,255,255,0.06); }}
#content img {{ max-width: 100%; height: auto; border-radius: 6px; }}
#content a {{ color: #38bdf8; text-decoration: none; }}
#content a:hover {{ text-decoration: underline; }}
.mermaid-container {{ text-align: center; margin: 1em 0; }}
.mermaid-container svg {{ max-width: 100%; }}
.mermaid-error {{ color: #ef4444; font-size: 0.9em; }}

body.light-mode {{
    background: #f1f5f9;
    color: #0f172a;
}}
body.light-mode #content code {{
    background: rgba(0,0,0,0.05);
    color: #0f172a;
}}
body.light-mode #content pre {{
    background: #cbd5e1;
}}
body.light-mode #content pre code {{
    color: #0f172a;
}}
body.light-mode #content blockquote {{
    color: rgba(15,23,42,0.7);
    border-left-color: #0284c7;
}}
body.light-mode #content table th {{
    background: rgba(0,0,0,0.03);
}}
body.light-mode #content th, body.light-mode #content td {{
    border-color: #cbd5e1;
}}
body.light-mode #content a {{
    color: #0284c7;
}}
</style>
</head>
<body>
<script>
// 立即从 localStorage 恢复主题，防止黑屏闪烁
const savedTheme = localStorage.getItem('theme') || 'dark';
if (savedTheme === 'light') {{
    document.body.classList.add('light-mode');
}}
</script>
<a id="back-btn" href="/" target="_self">← 返回</a>
<div id="content"></div>

<!-- KaTeX JS -->
<script src="/static/js/katex.min.js"></script>
<script src="/static/js/auto-render.min.js"></script>
<script>
// 将原始 MD 内容嵌入页面
const rawMd = {json.dumps(content)};

// 配置 marked
marked.setOptions({{
    breaks: true,
    gfm: true,
}});

function renderMarkdown(text) {{
    if (!text) return '';

    // 1. 保护 Mermaid 代码块,避免被 marked 解析
    const mermaidBlocks = [];
    text = text.replace(/```mermaid\\n([\\s\\S]*?)```/g, (match, code) => {{
        const placeholder = `%%MERMAID_${{mermaidBlocks.length}}%%`;
        mermaidBlocks.push(code.trim());
        return placeholder;
    }});

    // 2. 保护数学公式,避免被 marked 解析
    const mathBlocks = [];
    // 块级公式 $$...$$
    text = text.replace(/\\$\\$([\\s\\S]*?)\\$\\$/g, (match, formula) => {{
        const placeholder = `%%MATH_BLOCK_${{mathBlocks.length}}%%`;
        mathBlocks.push({{ formula: formula.trim(), display: true }});
        return placeholder;
    }});
    // 行内公式 $...$
    text = text.replace(/\\$([^$\\n]+?)\\$/g, (match, formula) => {{
        const placeholder = `%%MATH_INLINE_${{mathBlocks.length}}%%`;
        mathBlocks.push({{ formula: formula.trim(), display: false }});
        return placeholder;
    }});

    // 3. 用 marked 渲染 Markdown
    let html = marked.parse(text);

    // 4. 还原并渲染 KaTeX 数学公式
    mathBlocks.forEach((item, i) => {{
        const blockKey = `%%MATH_BLOCK_${{i}}%%`;
        const inlineKey = `%%MATH_INLINE_${{i}}%%`;
        const key = item.display ? blockKey : inlineKey;
        try {{
            const rendered = katex.renderToString(item.formula, {{
                displayMode: item.display,
                throwOnError: false,
                trust: true
            }});
            html = html.replace(key, rendered);
        }} catch (e) {{
            html = html.replace(key, item.display ? '$$' + item.formula + '$$' : '$' + item.formula + '$');
        }}
    }});

    // 5. 还原 Mermaid 占位符
    mermaidBlocks.forEach((code, i) => {{
        const containerId = `mermaid-docs-${{i}}`;
        const container = `<div class="mermaid-container" id="${{containerId}}" data-mermaid-code="${{encodeURIComponent(code)}}">`
            + `<div class="mermaid-loading">🔄 图表加载中...</div></div>`;
        html = html.replace(`%%MERMAID_${{i}}%%`, container);
    }});

    return html;
}}

document.getElementById('content').innerHTML = renderMarkdown(rawMd);

// 异步渲染 Mermaid 图表
(async () => {{
    try {{
        const savedTheme = localStorage.getItem('theme') || 'dark';
        const mermaidTheme = savedTheme === 'light' ? 'default' : 'dark';
        mermaid.initialize({{ startOnLoad: false, theme: mermaidTheme }});
        const containers = document.querySelectorAll('.mermaid-container');
        for (const container of containers) {{
            const code = decodeURIComponent(container.dataset.mermaidCode);
            try {{
                const {{ svg }} = await mermaid.render(`mermaid-svg-${{Date.now()}}-${{container.id}}`, code);
                container.innerHTML = svg;
            }} catch (e) {{
                container.innerHTML = `<div class="mermaid-error">⚠️ Mermaid 渲染失败: ${{e.message}}</div>`;
            }}
        }}
    }} catch (e) {{
        console.error('Mermaid render error:', e);
    }}
}})();
</script>
</body>
</html>'''
            return HTMLResponse(html_page)
        
        else:
            return HTMLResponse("<h1>不支持的文件类型</h1>", status_code=400)
    
    except Exception as e:
        return HTMLResponse(f"<h1>读取失败</h1><p>{str(e)}</p>", status_code=500)

# ========== TTS 端点（本地处理） ==========

@app.get("/api/tts")
async def api_tts(text: str, engine: str = "edge"):
    """TTS 语音合成（本地处理，不经过 AI Worker）"""
    import hashlib
    ext = ".wav" if engine == "sherpa" else ".mp3"
    media_type = "audio/wav" if engine == "sherpa" else "audio/mpeg"
    filename = hashlib.md5(f"{engine}:{text}".encode()).hexdigest() + ext
    filepath = os.path.join(AUDIO_DIR, filename)
    
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type=media_type)
    
    tts_engine.set_mode(engine)
    return StreamingResponse(tts_engine.stream_speech(text), media_type=media_type)

@app.post("/api/run_script")
async def run_script(request: Request):
    try:
        data = await request.json()
        script_type = data.get("type")
        device_id = data.get("device_id", "0")
        
        print(f"DEBUG: 尝试启动脚本 type={script_type}, device_id={device_id}")
        
        # 使用绝对路径定位 venv
        venv_python = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            # 备选路径 (针对不同安装环境)
            venv_python = os.path.join(BASE_DIR, "venv312", "Scripts", "python.exe")
            if not os.path.exists(venv_python):
                # 尝试当前环境下的解释器（如果 web_app.py 也是在 venv 下运行）
                venv_python = sys.executable if "venv" in sys.executable.lower() else "python"
            
        # 从请求中获取模型名称，如果没有则使用默认值
        model_name = data.get("model", "qwen2.5:3b")
        
        if script_type == "trans":
            # 同传模式：使用指定的 Ollama 模型
            script_file = os.path.join(BASE_DIR, "qwen3_realtime_trans.py")
            cmd_args = [venv_python, script_file, "--device_id", str(device_id), "--chunk", "1.5", "--model_size", "1.7B", "--model_type", "ollama", "--ollama_model", model_name]
        elif script_type == "trans_local":
            # 殿堂级推荐：本地 GPU 4-bit 翻译加速版 (1.7B ASR + 1.5B 4-bit 本地模型)
            script_file = os.path.join(BASE_DIR, "qwen3_realtime_trans.py")
            cmd_args = [venv_python, script_file, "--device_id", str(device_id), "--chunk", "2.5", "--model_size", "1.7B", "--model_type", "1.5b"]
        else:
            # 纯转录模式
            script_file = os.path.join(BASE_DIR, "qwen3_realtime.py")
            cmd_args = [venv_python, script_file, "--device_id", str(device_id), "--chunk", "2.5", "--model_size", "1.7B"]

        # 1. 清理旧进程
        if "active_task" in running_processes:
            p_old = running_processes["active_task"]
            print(f"DEBUG: 正在清理旧进程 PID={p_old.pid}")
            try:
                parent = psutil.Process(p_old.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                p_old.wait(timeout=2) # 等待释放
            except Exception as pe:
                print(f"DEBUG: 清理进程时发生异常 (可能已退出): {pe}")

        # 2. 启动新进程
        # 直接使用 python 启动，不再包裹 cmd /c 以避免路径解析和子进程残留问题
        # 同时将输出重定向到日志文件以便排查
        log_file_path = os.path.join(BASE_DIR, "logs", f"script_{script_type}.log")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        log_file = open(log_file_path, "a", encoding="utf-8")
        log_file.write(f"\n\n--- Start at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log_file.write(f"Command: {' '.join(cmd_args)}\n")
        log_file.flush()

        # Windows 特有：使用 CREATE_NEW_CONSOLE (0x10) 弹出新窗口
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = 0x00000010 
            
        # 注意：不再使用 debug_cmd，直接使用 cmd_args 列表
        new_p = subprocess.Popen(
            cmd_args, 
            creationflags=creation_flags, 
            cwd=BASE_DIR,
            stdout=log_file,
            stderr=log_file,
            env=os.environ.copy() # 确保继承环境变量
        )
        running_processes["active_task"] = new_p
        
        return {"status": "success", "message": f"成功启动，PID: {new_p.pid} (日志: logs/script_{script_type}.log)"}
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"🚨 run_script 崩溃:\n{error_trace}")
        return {"status": "error", "message": str(e)}


# ========== GPU 监控（本地处理） ==========

@app.get("/api/gpu_stats")
async def gpu_stats():
    """GPU 显存监控（SSE 流）"""
    async def event_generator():
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        while not is_shutting_down:
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                data = {
                    "memory_used": round(mem_info.used / (1024**3), 2),
                    "memory_total": round(mem_info.total / (1024**3), 2),
                    "utilization": util_info.gpu,
                    "temperature": temp
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception:
                pass
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ========== AI 代理端点 ==========

@app.post("/api/release_gpu")
async def release_gpu():
    """释放显存 — 终止 AI Worker 子进程，显存归零"""
    result = ai_worker.kill()
    return result

@app.get("/api/audio_devices")
async def get_audio_devices():
    """获取系统音频输入设备列表"""
    import sounddevice as sd
    devices = []
    try:
        device_list = sd.query_devices()
        for i, dev in enumerate(device_list):
            # 只要输入设备
            if dev['max_input_channels'] > 0:
                devices.append({
                    "id": i,
                    "name": dev['name'],
                    "hostapi": dev['hostapi'],
                    "max_input_channels": dev['max_input_channels'],
                    "default_samplerate": dev['default_samplerate']
                })
        return {"devices": devices}
    except Exception as e:
        logger.error(f"获取音频设备失败: {e}")
        return {"devices": [], "error": str(e)}

@app.get("/api/worker_status")
async def worker_status():
    """查询 AI Worker 状态"""
    return ai_worker.get_status()

@app.get("/api/ollama_status")
async def get_ollama_status():
    """获取 Ollama 的当前运行状态及模型资源分配关系"""
    # 默认从配置或本地获取 Ollama 的 API 地址
    ollama_url = config.get("models.llm_models.qwen-ollama-3b.api_url", "http://127.0.0.1:11434/v1/chat/completions")
    from urllib.parse import urlparse
    parsed = urlparse(ollama_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "http://127.0.0.1:11434"
    
    ps_url = f"{base_url}/api/ps"
    
    try:
        resp = await http_client.get(ps_url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get("models", [])
            if not models:
                return {
                    "running": True,
                    "has_model": False,
                    "message": "服务在线 (无运行模型)"
                }
            else:
                # 获取当前所有加载的模型资源信息
                models_info = []
                for model in models:
                    name = model.get("name", "Unknown")
                    size = model.get("size", 0)
                    size_vram = model.get("size_vram", 0)
                    
                    vram_gb = round(size_vram / (1024**3), 2)
                    ram_gb = round((size - size_vram) / (1024**3), 2)
                    total_gb = round(size / (1024**3), 2)
                    
                    vram_percent = round((size_vram / size) * 100, 1) if size > 0 else 0.0
                    
                    models_info.append({
                        "name": name,
                        "vram_gb": vram_gb,
                        "ram_gb": ram_gb,
                        "total_gb": total_gb,
                        "vram_percent": vram_percent
                    })
                
                try:
                    async with httpx.AsyncClient(timeout=2.0) as health_client:
                        resp = await health_client.get(f"{AI_WORKER_URL}/health")
                        if resp.status_code != 200:
                            raise Exception("health check failed")
                except Exception:
                    async def error_gen():
                        yield (json.dumps({"status": "error", "message": "AI Worker 启动失败"}) + "\n").encode("utf-8")
                    return StreamingResponse(
                        error_gen(),
                        media_type="text/plain",
                        headers={
                            "Cache-Control": "no-cache",
                            "X-Accel-Buffering": "no",
                            "Connection": "keep-alive"
                        }
                    )
                return {
                    "running": True,
                    "has_model": True,
                    "models": models_info,
                    "message": f"正在运行 {len(models_info)} 个模型"
                }
    except Exception as e:
        # 仅在 debug 日志记录，避免控制台刷屏
        logger.debug(f"Ollama stats query failed: {e}")
            
    return {
        "running": False,
        "has_model": False,
        "message": "未检测到服务"
    }

@app.get("/api/model_status")
async def model_status():
    """查询模型状态（代理到 worker）"""
    return await proxy_to_worker("GET", "/gpu_stats")

@app.get("/api/pytorch_memory")
async def pytorch_memory():
    """查询 PyTorch 内存（代理到 worker）"""
    return await proxy_to_worker("GET", "/gpu_stats")

@app.get("/api/models")
async def api_models():
    """查询可用模型列表（代理到 worker）"""
    return await proxy_to_worker("GET", "/api/models")

@app.post("/api/switch_model")
async def api_switch_model(request: SwitchModelRequest):
    """切换对话模型（代理到 worker）"""
    return await proxy_to_worker("POST", "/api/switch_model", json=request.model_dump())

@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """AI 对话（代理到 worker）"""
    if not ai_worker.ensure_running():
        return {"response": "⚠️ AI Worker 启动中，请稍后重试..."}
    
    try:
        resp = await http_client.post(f"{AI_WORKER_URL}/api/chat", json=request.model_dump(), timeout=120.0)
        return resp.json()
    except Exception as e:
        return {"response": f"❌ AI Worker 连接失败: {e}"}

@app.post("/api/chat_stream")
async def api_chat_stream(request: ChatRequest):
    """流式对话（代理到 worker，SSE 流）"""
    if not ai_worker.ensure_running():
        async def error_gen():
            yield 'data: {"token": "⚠️ AI Worker 启动中，请稍后重试..."}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    req = http_client.build_request("POST", f"{AI_WORKER_URL}/api/chat_stream", json=request.model_dump(), timeout=None)
    resp = await http_client.send(req, stream=True)
    
    async def stream_gen():
        try:
            async for chunk in resp.aiter_bytes():
                if chunk:
                    yield chunk
        finally:
            await resp.aclose()
    
    return StreamingResponse(
        stream_gen(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

# ========== 联网搜索 API 代理 ==========

@app.get("/api/search/status")
async def api_search_status():
    """获取搜索功能状态"""
    if not ai_worker.ensure_running():
        return {"enabled": False, "message": "AI Worker 未运行"}
    
    try:
        resp = await http_client.get(f"{AI_WORKER_URL}/api/search/status", timeout=10.0)
        return resp.json()
    except Exception as e:
        return {"enabled": False, "message": f"查询失败: {e}"}

class VoiceDesignRequest(BaseModel):
    voice_prompt: str
    text: str

@app.post("/api/voice_design")
async def api_voice_design(request: VoiceDesignRequest):
    """声音设计与语音合成（本地直连小米官方 API，忽略本地系统代理）"""
    logger.info(f"🎙️ 收到声音设计请求: prompt={request.voice_prompt[:30]}..., text={request.text[:30]}...")
    
    # 动态加载 API Key
    api_key = config.get("models.llm_models.mimo-v2.5-pro.api_key", "tp-ccp0qo9pnulek1fo2n93lpgt92z5fkkac9lb4p4tpny1rroo")
    
    url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mimo-v2.5-tts-voicedesign",
        "messages": [
            {"role": "user", "content": request.voice_prompt},
            {"role": "assistant", "content": request.text}
        ],
        "audio": {"format": "mp3"},
        "audio_format": "mp3"
    }
    
    try:
        import base64
        import requests
        
        # 强制禁用本地系统代理，直连极速公网
        resp = requests.post(url, json=payload, headers=headers, timeout=40, proxies={'http': None, 'https': None})
        
        if resp.status_code == 200:
            data = resp.json()
            audio_data_base64 = None
            
            # 兼容性多层级提取 base64
            try:
                audio_data_base64 = data['choices'][0]['message']['audio']['data']
            except:
                pass
                
            if not audio_data_base64:
                try:
                    content = data['choices'][0]['message']['content']
                    if len(content) > 1000 and (content.startswith('/') or content.startswith('i')):
                        audio_data_base64 = content
                except:
                    pass
            
            if not audio_data_base64:
                try:
                    audio_data_base64 = data['audio']['data']
                except:
                    pass
            
            if audio_data_base64:
                # 完美解码并存入静态音频缓存目录
                import time
                filename = f"designed_voice_{int(time.time())}.mp3"
                filepath = os.path.join(AUDIO_DIR, filename)
                
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(audio_data_base64))
                
                web_url = f"/static/audio/{filename}"
                logger.info(f"✓ 声音设计合成成功: {web_url}")
                return {"status": "success", "url": web_url}
            else:
                logger.error("未能在 API 响应体中找到 Base64 音频")
                return {"status": "error", "message": "API 未返回有效的音频数据"}
        else:
            logger.error(f"小米 API 报错: {resp.status_code} - {resp.text}")
            return {"status": "error", "message": f"小米 API 报错: {resp.status_code}"}
            
    except Exception as e:
        logger.error(f"声音设计接口异常: {e}")
        return {"status": "error", "message": str(e)}

# 注意：搜索功能已集成到 /api/chat_stream 中，无需单独的 /api/search 端点

@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    """文本总结（代理到 worker，流式）"""
    if not ai_worker.ensure_running():
        async def error_gen():
            yield (json.dumps({"status": "error", "message": "AI Worker 启动失败"}) + "\n").encode("utf-8")
        return StreamingResponse(
            error_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    
    # 注意：上下文管理器必须放在生成器内部，否则 resp 会过早关闭
    async def stream_gen():
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", f"{AI_WORKER_URL}/api/summarize", json=request.model_dump()) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        except Exception as e:
            logger.error(f"流式代理错误: {e}")
            yield (json.dumps({"status": "error", "message": str(e)}) + "\n").encode("utf-8")
    
    return StreamingResponse(
        stream_gen(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@app.post("/api/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    model_size: Optional[str] = Form("1.7B"),
):
    """视频转录（代理到 worker）"""
    if not ai_worker.ensure_running():
        async def error_gen():
            yield (json.dumps({"status": "error", "message": "AI Worker 启动失败"}) + "\n").encode("utf-8")
        return StreamingResponse(
            error_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    
    # 直接转发文件到 worker
    async def stream_gen():
        async with httpx.AsyncClient(timeout=600.0) as client:
            files = {"file": (file.filename, await file.read(), file.content_type)}
            data = {}
            if language:
                data["language"] = language
            if model_size:
                data["model_size"] = model_size
            async with client.stream("POST", f"{AI_WORKER_URL}/api/transcribe", files=files, data=data) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
    return StreamingResponse(
        stream_gen(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@app.post("/api/transcribe_path")
async def api_transcribe_path(
    path: str = Form(...),
    language: Optional[str] = Form(None),
    model_size: Optional[str] = Form("1.7B"),
):
    """本地路径转录（代理到 worker）"""
    if not ai_worker.ensure_running():
        async def error_gen():
            yield (json.dumps({"status": "error", "message": "AI Worker 启动失败"}) + "\n").encode("utf-8")
        return StreamingResponse(
            error_gen(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )
    
    async def stream_gen():
        async with httpx.AsyncClient(timeout=600.0) as client:
            req_body = {
                "path": path,
                "language": language,
                "model_size": model_size
            }
            async with client.stream("POST", f"{AI_WORKER_URL}/api/transcribe_path", json=req_body) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
    return StreamingResponse(
        stream_gen(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

# ========== 文件操作端点 ==========

@app.get("/api/download_srt")
async def download_srt(path: str):
    """下载 SRT 字幕"""
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    
    if not os.path.exists(path):
        return {"error": "File not found"}
    
    import urllib.parse
    filename = os.path.basename(path)
    encoded_filename = urllib.parse.quote(filename)
    
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    return FileResponse(path, media_type='application/x-subrip', headers=headers)

@app.post("/api/open_recordings")
async def open_recordings():
    """打开录音文件夹"""
    try:
        import subprocess
        subprocess.Popen(f'explorer "{RECORDINGS_DIR}"')
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== 知识库 API 代理 ==========

@app.middleware("http")
async def proxy_kb_api(request: Request, call_next):
    """拦截 /api/kb/* 与 /api/wechat/* 请求并代理到 AI Worker"""
    if not request.url.path.startswith("/api/kb/") and not request.url.path.startswith("/api/wechat/"):
        return await call_next(request)
    
    try:
        if not ai_worker.ensure_running():
            return JSONResponse({"error": "AI Worker 未运行"}, status_code=503)
        
        target_path = request.url.path
        if request.url.query:
            target_path = f"{target_path}?{request.url.query}"
        url = f"{AI_WORKER_URL}{target_path}"
        body = await request.body()

        # SSE 流式端点：逐字节转发，不缓冲
        if "_stream" in request.url.path:
            req = http_client.build_request(
                request.method, url,
                content=body or None,
                headers={"Content-Type": request.headers.get("content-type", "application/json")}
            )
            resp = await http_client.send(req, stream=True)

            async def stream_gen():
                try:
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            yield chunk
                finally:
                    await resp.aclose()

            return StreamingResponse(
                stream_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
            )

        # 普通请求：等待完整响应
        resp = await http_client.request(
            request.method, url,
            content=body or None,
            headers={"Content-Type": request.headers.get("content-type", "application/json")}
        )
        
        response_headers = {}
        for key, value in resp.headers.items():
            if key.lower() not in ("content-encoding", "transfer-encoding", "content-length"):
                response_headers[key] = value
        
        return Response(content=resp.content, status_code=resp.status_code, headers=response_headers, media_type=resp.headers.get("content-type", "application/json"))
    except Exception as e:
        logger.error(f"KB 代理错误: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/analytics/digest")
async def api_analytics_digest(request: DigestRequest):
    """为指定群聊在特定日期（或近期）的消息生成 AI 纪要"""
    if not ai_worker.ensure_running():
        async def error_gen():
            yield 'data: {"error": "AI Worker 启动失败"}\n\n'.encode("utf-8")
        return StreamingResponse(error_gen(), media_type="text/event-stream")
        
    try:
        from chat_analytics import ChatAnalytics
        analytics = ChatAnalytics()
        cursor = analytics.conn.cursor()
        
        session_id = request.session_id
        date = request.date
        
        # 1. 获取群昵称映射
        cursor.execute("""
            SELECT wxid, wechat_name, nickname 
            FROM group_members 
            WHERE session_id = ?
        """, (session_id,))
        member_rows = cursor.fetchall()
        
        wxid_to_group_name = {}
        wechat_name_to_group_name = {}
        for row in member_rows:
            wxid = row[0]
            wechat_name = row[1]
            group_name = row[2]
            if not group_name or group_name.strip() in ('-', ''):
                group_name = wechat_name if wechat_name and wechat_name.strip() not in ('-', '') else wxid
            if group_name:
                wxid_to_group_name[wxid] = group_name
                if wechat_name:
                    wechat_name_to_group_name[wechat_name] = group_name
                    
        # 2. 查询消息记录
        if date:
            cursor.execute("""
                SELECT sender_display_name, content, formatted_time, sender_username 
                FROM messages 
                WHERE session_id = ? AND formatted_time LIKE ? AND type IN ('text', '文本消息')
                ORDER BY create_time ASC
            """, (session_id, f"{date}%"))
            rows = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT sender_display_name, content, formatted_time, sender_username 
                FROM messages 
                WHERE session_id = ? AND type IN ('text', '文本消息')
                ORDER BY create_time DESC 
                LIMIT 400
            """, (session_id,))
            rows = cursor.fetchall()[::-1]
            
        if not rows:
            async def empty_gen():
                yield 'data: {"content": "📭 该日期（或近期）无任何文本消息记录，无法生成纪要。"}\n\n'.encode("utf-8")
            return StreamingResponse(empty_gen(), media_type="text/event-stream")
            
        # 3. 组装对话文本
        chat_lines = []
        for r in rows:
            sender_display = r[0]
            content = r[1] or ""
            formatted_time = r[2]
            sender_wxid = r[3]
            
            time_str = formatted_time.split(" ")[-1][:5] if formatted_time else ""
            sender_name = wxid_to_group_name.get(sender_wxid) or wechat_name_to_group_name.get(sender_display) or sender_display or "未知"
            chat_lines.append(f"[{time_str}] {sender_name}: {content}")
            
        chat_text = "\n".join(chat_lines)
        
        # 4. 构建提示词
        prompt = f"""你是一个智能微信群聊纪要助手。请为以下群聊记录生成一份结构化的‘月度群聊纪要与干货总结’。
        请用精炼的中文进行归纳，重点关注：
1. 讨论的核心主题（大家主要在聊什么）
2. 提及的具体学校或考点（如巴蜀、育才、八中等）及其相关讨论内容
3. 推荐的课外书籍、练习册、教辅（如《知识清单》等）
4. 提及的培训机构与辅导品牌（如学而思、新东方等）
5. 重要通知、后续活动或群友共识（如交表时间、家长会、免单活动等）

以下为群聊对话记录：
---
{chat_text}
---
请直接以结构化 Markdown 形式输出纪要，不要包含任何前导或后续多余的客套话。"""

        # 5. 调用 AI Worker 的 /api/chat_stream
        chat_payload = {
            "messages": [{"role": "user", "content": prompt}],
            "enable_search": False,
            "enable_think": False
        }
        
        async def stream_gen():
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    async with client.stream("POST", f"{AI_WORKER_URL}/api/chat_stream", json=chat_payload) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
            except Exception as e:
                logger.error(f"AI 纪要流式处理出错: {e}")
                yield f'data: {{"error": "{str(e)}"}}\n\n'.encode("utf-8")
                
        return StreamingResponse(stream_gen(), media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"生成群聊纪要失败: {e}")
        async def error_gen():
            yield f'data: {{"error": "{str(e)}"}}\n\n'.encode("utf-8")
        return StreamingResponse(error_gen(), media_type="text/event-stream")


# ========== 启动 ==========

if __name__ == "__main__":
    import uvicorn
    logger.info(f"主服务启动在 http://0.0.0.0:8000")
    logger.info(f"AI Worker 将在首次使用时启动（端口 {AI_WORKER_PORT}）")
    logger.info("点击「释放显存」将终止 AI Worker，显存完全释放")
    
    # 禁用 uvicorn 默认的 ANSI 彩色日志，避免非 TTY 环境下出现 [32m 乱码
    import uvicorn as _uv
    log_cfg = _uv.config.LOGGING_CONFIG.copy()
    log_cfg["formatters"]["default"]["()"] = "uvicorn.logging.DefaultFormatter"
    log_cfg["formatters"]["default"]["use_colors"] = False
    log_cfg["formatters"]["access"]["()"] = "uvicorn.logging.AccessFormatter"
    log_cfg["formatters"]["access"]["use_colors"] = False

    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_graceful_shutdown=3, log_config=log_cfg)
