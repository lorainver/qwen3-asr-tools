"""
ai_worker.py - AI 推理独立子进程

运行在端口 8001，处理所有需要 GPU 的任务：
- /api/chat — AI 对话
- /api/summarize — 文本总结
- /api/transcribe — 视频转录
- /api/transcribe_path — 本地路径转录

进程生命周期：
- 由 web_app.py 启动（需要 AI 时）
- 由 web_app.py 终止（释放显存）
- 进程退出后，CUDA context 完全释放 → 显存归零
"""

import os
import argparse
import torch
import pynvml
import logging
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from summarizer import LongTextSummarizer
from transcriber import run_transcription
from config_loader import config

# 配置日志
logging.basicConfig(
    level=logging.getLevelName(config.get('logging.level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.get('logging.file', 'logs/ai_worker.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 初始化 FastAPI
app = FastAPI(title="AI Worker (GPU Inference)")

# 初始化 NVML（用于 GPU 状态上报）
pynvml.nvmlInit()

# 初始化模型
summarizer = LongTextSummarizer()

# ========== Pydantic 模型 ==========

class ChatRequest(BaseModel):
    messages: list

class SummarizeRequest(BaseModel):
    text: str

# ========== API 端点 ==========

@app.get("/health")
async def health():
    """健康检查，web_app.py 用于判断 worker 是否存活"""
    logger.info("Health check requested")
    return {"status": "ok", "service": "ai_worker"}

@app.get("/gpu_stats")
async def gpu_stats():
    """返回 GPU 状态（供 web_app.py 代理）"""
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
    
    # PyTorch 内存详情
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    
    logger.debug(f"GPU stats: allocated={allocated:.2f}GB, reserved={reserved:.2f}GB")
    return {
        "memory_used": round(mem_info.used / (1024**3), 2),
        "memory_total": round(mem_info.total / (1024**3), 2),
        "utilization": util_info.gpu,
        "temperature": temp,
        "allocated_gb": round(allocated, 3),
        "reserved_gb": round(reserved, 3)
    }

@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """AI 对话"""
    logger.info("Chat request received")
    response_text = summarizer.chat(request.messages)
    return {"response": response_text}

@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    """文本总结（流式）"""
    logger.info(f"Summarize request: text length={len(request.text)}")
    
    def generate():
        for res in summarizer.summarize(request.text, yield_progress=True):
            yield res + "\n"
    
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    """视频转录（上传文件）"""
    logger.info(f"Transcribe request: filename={file.filename}")
    
    # 保存上传文件
    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    
    file_location = os.path.join(recordings_dir, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())
    
    srt_location = os.path.join(recordings_dir, f"{file.filename.rsplit('.', 1)[0]}.srt")
    
    def generate():
        for res in run_transcription(file_location, srt_location, yield_progress=True):
            yield res
    
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/api/transcribe_path")
async def api_transcribe_path(path: str = Form(...)):
    """本地路径转录"""
    path = path.strip('"').strip("'")
    logger.info(f"Transcribe path request: {path}")
    
    if not os.path.exists(path):
        def error_gen():
            import json
            yield json.dumps({"status": "error", "message": f"文件不存在: {path}"}) + "\n"
        return StreamingResponse(error_gen(), media_type="text/plain")
    
    filename_stem = os.path.basename(path).rsplit('.', 1)[0]
    srt_location = os.path.join(os.path.dirname(path), f"{filename_stem}.srt")
    
    def generate():
        for res in run_transcription(path, srt_location, yield_progress=True):
            yield res
    
    return StreamingResponse(generate(), media_type="text/plain")

# ========== 启动 ==========

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001, help="Worker 端口")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Worker 主机")
    args = parser.parse_args()
    
    import uvicorn
    logger.info(f"[AI Worker] 启动在 {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
