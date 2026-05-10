import os
import pynvml
import asyncio
import json
import signal
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from summarizer import LongTextSummarizer
from transcriber import run_transcription
from tts_engine import TTSEngine

app = FastAPI(title="Qwen3 ASR Web Console")

# 获取当前脚本所在的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 使用绝对路径创建和挂载目录
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

pynvml.nvmlInit()
summarizer = LongTextSummarizer()
tts_engine = TTSEngine()

@app.get("/api/tts")
async def api_tts(text: str, engine: str = "edge"):
    """根据文本流式生成语音或返回缓存"""
    import hashlib

    # 根据引擎决定缓存文件格式
    ext = ".wav" if engine == "sherpa" else ".mp3"
    media_type = "audio/wav" if engine == "sherpa" else "audio/mpeg"
    filename = hashlib.md5(f"{engine}:{text}".encode()).hexdigest() + ext
    filepath = os.path.join(AUDIO_DIR, filename)
    
    # 1. 如果有缓存，直接返回（秒开）
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type=media_type)
            
    # 2. 没有缓存，流式生成
    tts_engine.set_mode(engine)
    return StreamingResponse(tts_engine.stream_speech(text), media_type=media_type)

@app.post("/api/shutdown")

async def shutdown():
    """彻底关闭服务器并释放显存 (Windows 兼容版)"""
    import threading
    import time

    def delayed_exit():
        time.sleep(1) # 给前端 1 秒钟显示“服务器已停止”的提示
        print("正在强制退出并释放显存...")
        os._exit(0) # 强制结束进程，最有效释放显存的方式

    print("收到网页端关闭指令...")
    threading.Thread(target=delayed_exit).start()
    return {"status": "shutdown", "message": "Server will exit in 1s"}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    # 显式指定 request 参数
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/api/gpu_stats")
async def gpu_stats():
    """Stream GPU memory and utilization via Server-Sent Events"""
    async def event_generator():
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        while True:
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

class SummarizeRequest(BaseModel):
    text: str

@app.post("/api/summarize")
async def api_summarize(request: SummarizeRequest):
    """Stream summarize progress"""
    def generate():
        for res in summarizer.summarize(request.text, yield_progress=True):
            yield res + "\n"
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/api/transcribe_path")
async def api_transcribe_path(path: str = Form(...)):
    """直接根据本地绝对路径进行转录，不产生副本"""
    path = path.strip('"').strip("'")
    if not os.path.exists(path) and not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    if not os.path.exists(path):
        def error_gen():
            yield json.dumps({"status": "error", "message": f"错误：找不到文件 - {path}"}) + "\n"
        return StreamingResponse(error_gen(), media_type="text/plain")
    filename_stem = os.path.basename(path).rsplit('.', 1)[0]
    srt_location = os.path.join(os.path.dirname(path), f"{filename_stem}.srt")
    def generate():
        for res in run_transcription(path, srt_location, yield_progress=True):
            yield res
    return StreamingResponse(generate(), media_type="text/plain")

class ChatRequest(BaseModel):
    messages: list

# 必须添加这个接口
@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """通用对话接口"""
    # 这里的 summarizer 是你在文件上方已经创建好的对象
    response_text = summarizer.chat(request.messages)
    return {"response": response_text}


@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    file_location = os.path.join(RECORDINGS_DIR, file.filename)
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
        
    srt_location = os.path.join(RECORDINGS_DIR, f"{file.filename.rsplit('.', 1)[0]}.srt")

    def generate():
        for res in run_transcription(file_location, srt_location, yield_progress=True):
            yield res
            

@app.get("/api/download_srt")
async def download_srt(path: str):
    """下载 SRT 字幕，处理文件名乱码并确保正确的文件名"""
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    
    if not os.path.exists(path):
        return {"error": "File not found"}

    filename = os.path.basename(path)
    # 使用 quote 对文件名进行 URL 编码，解决浏览器下载中文名乱码问题
    import urllib.parse
    encoded_filename = urllib.parse.quote(filename)
    
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    # 使用 application/x-subrip 作为 SRT 的标准媒体类型
    return FileResponse(path, media_type='application/x-subrip', headers=headers)

@app.post("/api/open_recordings")
async def open_recordings():
    """在本地打开录音/字幕文件夹 (Windows)"""
    try:
        import subprocess
        # 使用 explorer 直接打开文件夹
        subprocess.Popen(f'explorer "{RECORDINGS_DIR}"')
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # 启动时依然可以在 D 盘运行
    uvicorn.run(app, host="0.0.0.0", port=8000)
