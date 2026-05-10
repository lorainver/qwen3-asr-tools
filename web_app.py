import os
import pynvml
import asyncio
import json
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from summarizer import LongTextSummarizer
from transcriber import run_transcription

app = FastAPI(title="Qwen3 ASR Web Console")

# 获取当前脚本所在的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 使用绝对路径创建和挂载目录
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

pynvml.nvmlInit()
summarizer = LongTextSummarizer()

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

# 必须添加这个类定义
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
            
    return StreamingResponse(generate(), media_type="text/plain")

@app.get("/api/download_srt")
async def download_srt(path: str):
    # path 如果是相对路径，转为绝对路径
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return FileResponse(path, media_type='text/plain', filename=os.path.basename(path))

if __name__ == "__main__":
    import uvicorn
    # 启动时依然可以在 D 盘运行
    uvicorn.run(app, host="0.0.0.0", port=8000)
