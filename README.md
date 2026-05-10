# Qwen3-ASR AI 智能音视频工作站

这是一个基于 **Qwen3-ASR** 和 **Qwen2.5** 大模型构建的本地化音视频处理工作站。它集成了语音转文字、长文本 AI 总结、本地智能对话以及 GPU 实时监控功能。

---

## 🌟 核心功能 (Web 界面)

- **🚀 极速视频转录 (ASR)**: 基于 `Qwen3-ASR-1.7B` 模型，支持 GPU 批处理加速。
- **📝 智库级文本总结**: 集成 `Qwen2.5-1.5B-Instruct` 模型，支持超长文本分段总结。
- **💬 本地 AI 助理**: 类似 ChatGPT 的对话界面，支持上下文记忆。
  - **✨ 新增**: **[新建对话]** 按钮，可一键清空对话记录，重置 AI 记忆并提升响应速度。
- **📊 GPU 实时看板**: 监控显存、利用率及温度。
  - **✨ 新增**: **[停止服务器]** 按钮，点击后自动卸载模型并关闭进程，瞬间释放 100% 显存。
- **🎨 现代 Web UI**: 采用 Glassmorphism 风格，内置 **[终端实战命令参考]** 区域，支持点击代码块自动复制。

---

## ⌨️ 命令行实战工具 (CLI)

网页版最下方提供了完整的命令参考。以下是常用范例：

### 1. 字幕提取 (SRT)
- **Qwen3 GPU 极速版**:
  `D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_full_srt.py "视频路径" --chunk 10 --batch 12`
- **Whisper CPU/通用版**:
  `D:\Programs\Python\Python314\python.exe D:\qwen3-asr\fw_srt.py "视频路径" --beam 1`

### 2. 实时语音监控 (GUI)
- **带翻译 (双语对照)**:
  `python qwen3_realtime_trans.py --device_id 30 --chunk 1.5`
- **系统声音识别 (无翻译)**:
  `python qwen3_realtime.py --device_id 30 --chunk 1.0`

---

## 🛠️ 运行与维护

1. **启动服务**:
   ```powershell
   D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\web_app.py
   ```
2. **显存释放**:
   - 若需运行其他高显存应用，请点击网页侧边栏的“停止服务器”按钮。
   - 也可以在终端按 `Ctrl + C`，但点击网页按钮响应更直接。
3. **记忆管理**:
   - 对话历史较长时会增加显存占用，建议定期使用“新建对话”重置。

## 🔒 隐私声明

所有模型推理均在**本地 GPU** 完成，100% 离线运行，确保数据隐私安全。
