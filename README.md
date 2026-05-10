# Qwen3-ASR AI 智能音视频工作站
这是一个基于 **Qwen3-ASR** 和 **Qwen2.5** 大模型构建的本地化音视频处理工作站。它集成了语音转文字、长文本 AI 总结、本地智能对话、AI 语音朗读以及 GPU 实时监控功能。
---
## 🌟 核心功能 (Web 界面)
- **🚀 极速视频转录 (ASR)**: 基于 `Qwen3-ASR-1.7B` 模型，支持 GPU 批处理加速。
- **📝 智库级文本总结**: 集成 `Qwen2.5-1.5B-Instruct` 模型，支持超长文本分段总结。
- **💬 本地 AI 助理**: 类似 ChatGPT 的对话界面，支持上下文记忆。
  - **[新建对话]** 按钮：一键清空对话记录，重置 AI 记忆并提升响应速度。
- **🔊 AI 语音朗读 (TTS)**: 每条 AI 回复旁均有 🔊 按钮，点击即可朗读，再次点击停止。
  - **🌐 微软在线 (Edge-TTS)**：高质量在线语音，流式传输，响应极快。
  - **🏠 本地离线 (Sherpa-ONNX)**：基于 `vits-icefall-zh-aishell3` 模型，完全离线，网络差时首选。
  - 可在网页右上角下拉菜单随时切换两种模式。
  - **[自动朗读]** 开关：开启后 AI 回复完成时自动朗读，无需手动点击。
- **📊 GPU 实时看板**: 监控显存、利用率及温度。
  - **[停止服务器]** 按钮：点击后自动关闭进程，瞬间释放显存。
- **🎨 现代 Web UI**: Glassmorphism 风格，内置终端命令参考，支持代码块一键复制。
---
## 🔊 语音朗读部署说明
### 在线引擎 (Edge-TTS)
无需额外配置，启动服务后即可使用。
### 离线引擎 (Sherpa-ONNX) 首次部署
运行以下脚本自动下载并配置离线模型（约 45MB）：
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\download_tts_model.py
模型将保存至 D:\qwen3-asr\models\tts\vits-icefall-zh-aishell3\。

⌨️ 命令行实战工具 (CLI)
1. 字幕提取 (SRT)
Qwen3 GPU 极速版: D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_full_srt.py "视频路径" --chunk 10 --batch 12
Whisper CPU/通用版: D:\Programs\Python\Python314\python.exe D:\qwen3-asr\fw_srt.py "视频路径" --beam 1
2. 实时语音监控 (GUI)
带翻译 (双语对照): D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_realtime_trans.py --device_id 30 --chunk 1.5
系统声音识别 (无翻译): D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_realtime.py --device_id 30 --chunk 1.0

🛠️ 运行与维护
启动服务:
powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\web_app.py
显存释放:
若需运行其他高显存应用，请点击网页侧边栏的"停止服务器"按钮。
也可以在终端按 Ctrl + C，但点击网页按钮响应更直接。
记忆管理:
对话历史较长时会增加显存占用，建议定期使用"新建对话"重置。
语音引擎切换:
网络正常时推荐使用"🌐 微软在线"，音质更佳。
网络差或追求极致响应时切换至"🏠 本地离线"。
🔒 隐私声明
所有 AI 模型推理（ASR、文本总结、对话）均在本地 GPU 完成，100% 离线运行。 在线 TTS 语音朗读功能会将文本发送至微软服务器；如需完全离线，请使用"本地离线"模式。