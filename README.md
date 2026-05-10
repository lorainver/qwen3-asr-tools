# Qwen3-ASR AI 智能音视频工作站

这是一个基于 **Qwen3-ASR** 和 **Qwen2.5** 大模型构建的本地化音视频处理工作站。

---

## 🖥️ Web 界面功能 (快速启动)

### 核心功能
- **🚀 极速视频转录 (ASR)**: 自动批处理加速。
- **📝 智库级文本总结**: 处理超长会议纪要。
- **💬 本地 AI 助理**: 具备上下文记忆的对话模式。
- **📊 GPU 实时看板**: 监控显存、利用率及温度。

### 启动方式
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\web_app.py
```
访问：`http://127.0.0.1:8000`

---

## ⌨️ 命令行实战命令范例 (CLI)

以下是针对不同场景优化的命令示例，请根据需要复制使用：

### 1. 字幕提取 (生成 SRT 文件)

#### **Qwen3 高精度转录 (推荐 GPU 用户)**
*支持批处理，速度极快：*
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_full_srt.py "F:\屏幕录制\乐学猫直播 2026-05-07 20-04-21-162.mp4" --chunk 10 --batch 12
```

#### **Whisper 转录 (CPU/通用)**
*建议使用 `--beam 1` 以获得最快识别速度：*
```powershell
D:\Programs\Python\Python314\python.exe D:\qwen3-asr\fw_srt.py "F:\屏幕录制\bandicam 2026-05-07 20-04-21-162.mp4" --beam 1
```

---

### 2. 实时字幕显示 (GUI)

#### **带翻译的实时显示 (双语对照)**
*适用于观看外语直播或外语会议，设备 ID 30 为虚拟音频输入：*
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_realtime_trans.py --device_id 30 --chunk 1.5
```

#### **Chrome/系统声音实时识别 (不带翻译)**
*实时监听系统播放的内容：*
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_realtime.py --device_id 30 --chunk 1.0
```

#### **麦克风实时录音识别**
*适用于现场演讲、个人录音场景（假设麦克风设备 ID 为 1）：*
```powershell
D:\qwen3-asr\venv\Scripts\python.exe D:\qwen3-asr\qwen3_realtime.py --device_id 1 --chunk 2.0
```

---

## 💡 参数说明

- `--device_id`: 输入音频设备 ID（可用相关的 list 命令查询）。
- `--chunk`: 处理的音频块长度（秒），越小延迟越低，越大识别越稳。
- `--batch`: 批处理大小，越大越压榨 GPU 性能。
- `--beam`: 束搜索宽度，`1` 为贪婪搜索（速度最快）。

## 🔒 隐私与运行环境

- **运行环境**: `D:\qwen3-asr\venv` (已预装所有依赖)。
- **隐私**: 100% 本地运行，无需网络连接。
