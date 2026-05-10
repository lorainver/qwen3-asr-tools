# Qwen3-ASR AI 智能音视频工作站

这是一个基于 **Qwen3-ASR** 和 **Qwen2.5** 大模型构建的本地化音视频处理工作站。它集成了语音转文字、长文本 AI 总结、本地智能对话以及 GPU 实时监控功能，旨在提供一个私密、高效且免费的 AI 生产力工具。

## 🌟 核心功能

- **🚀 极速视频转录 (ASR)**: 基于 `Qwen3-ASR-0.6B` 模型，支持 GPU 批处理 (Batch Processing) 加速，识别速度可达视频长度的 10-20 倍。
- **📝 智库级文本总结**: 集成 `Qwen2.5-1.5B-Instruct` 模型，采用 Map-Reduce 分治算法，支持处理超长会议纪要并输出结构化精华。
- **💬 本地 AI 助理**: 提供类似 ChatGPT 的网页对话界面，支持上下文记忆，完全在本地 RTX 显卡上运行。
- **📊 GPU 实时看板**: 通过 SSE 技术实时监控显存占用、GPU 利用率及温度。
- **🎨 现代 Web UI**: 采用 Glassmorphism（暗黑玻璃拟物化）风格设计，支持文件拖拽上传及 SRT 字幕下载。

## 🛠️ 技术架构

- **后端**: FastAPI (Python 3.10+)
- **推理**: PyTorch, Transformers, BitsAndBytes (4-bit 量化优化)
- **监控**: pynvml (NVIDIA Management Library)
- **前端**: 原生 HTML5, Vanilla CSS, JavaScript (ES6+)

## 💻 硬件要求

- **GPU**: NVIDIA RTX 系列显卡（建议显存 8GB 及以上，如 RTX 3060/4060/5060）。
- **驱动**: CUDA 12.1+ 及对应的 cuDNN。

## 🚀 快速开始

1. **环境初始化**:
   ```powershell
   # 进入项目目录
   cd D:\qwen3-asr
   # 激活虚拟环境 (已配置)
   .\venv\Scripts\activate
   ```

2. **启动 Web 服务**:
   ```powershell
   python web_app.py
   ```

3. **访问界面**:
   打开浏览器访问 `http://127.0.0.1:8000`

## 📂 项目结构

- `web_app.py`: FastAPI 后端主入口。
- `summarizer.py`: 文本总结与对话推理引擎。
- `transcriber.py`: Qwen3-ASR 批处理转录引擎。
- `templates/`: 网页 HTML 模板。
- `static/`: 存放 CSS 样式、JS 逻辑及图标资源。
- `recordings/`: 默认的文件上传与字幕存储目录。

## 🔒 隐私声明

本项目所有模型推理均在**本地 GPU** 完成，不上传任何音频、视频或文本数据到云端，确保绝对的数据隐私。

---
*Created by Antigravity AI Assistant*
