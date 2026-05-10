# Qwen3-ASR AI 智能音视频工作站

这是一个基于 **Qwen3-ASR** 和 **Qwen2.5** 大模型构建的本地化音视频处理工作站。支持 Web 界面交互和多种强大的命令行脚本工具。

---

## 🖥️ Web 界面功能 (快速启动)

### 核心功能
- **🚀 极速视频转录 (ASR)**: 基于 `Qwen3-ASR-0.6B` 模型，支持 GPU 批处理加速。
- **📝 智库级文本总结**: 集成 `Qwen2.5-1.5B-Instruct` 模型，支持超长文本分段总结。
- **💬 本地 AI 助理**: 类似 ChatGPT 的对话界面，支持上下文记忆。
- **📊 GPU 实时看板**: SSE 技术监控显存、利用率及温度。

### 启动方式
```powershell
python web_app.py
```
访问：`http://127.0.0.1:8000`

---

## ⌨️ 命令行脚本工具 (高级功能)

除了 Web 页面，你还可以直接运行以下 Python 脚本来实现更专业的任务：

### 1. 视频转录工具 (生成 SRT 字幕)

#### **CPU 版本 (Faster-Whisper)**
适用于没有显卡或想节省显存的场景，使用 `faster-whisper` 引擎。
- **脚本**: `fw_srt.py`
- **运行方式**: `python fw_srt.py`

#### **GPU 版本 (Qwen3-ASR)**
利用 RTX 显卡进行高精度极速转录，支持批处理模式。
- **脚本**: `qwen3_full_srt.py`
- **运行方式**: `python qwen3_full_srt.py`

---

### 2. 实时语音监控工具 (GUI 界面)

#### **实时字幕显示 (大模型版)**
使用参数量更大的模型进行实时语音流识别，适合对精度要求极高的直播或会议场景。
- **脚本**: `qwen3_realtime.py`
- **特点**: 低延迟、高精度。
- **运行方式**: `python qwen3_realtime.py`

#### **带翻译的实时字幕显示**
在实时识别语音的同时，自动将识别结果翻译为目标语言，双语同步显示。
- **脚本**: `qwen3_realtime_trans.py`
- **特点**: 集成 Qwen2.5 翻译引擎，支持双语对照。
- **运行方式**: `python qwen3_realtime_trans.py`

---

## 🛠️ 环境要求

- **Python**: 3.10+ (建议在虚拟环境 `venv` 下运行)
- **GPU**: NVIDIA RTX 系列 (建议 8GB+ 显存)
- **依赖**: 见 `requirements.txt` (核心包含 `transformers`, `torch`, `fastapi`, `pynvml`, `bitsandbytes`)

## 📂 项目说明

- `web_app.py`: Web 后端。
- `summarizer.py`: 总结/对话引擎。
- `transcriber.py`: Web 端转录封装。
- `models/`: 存放 Qwen 系列本地模型。

## 🔒 隐私声明

100% 本地化运行，数据不出本地，确保隐私安全。
