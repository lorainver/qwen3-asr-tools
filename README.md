# Qwen3-ASR 离线转录与实时字幕工具

基于 Qwen3-ASR 模型的自动化音频处理工具集。

## 功能特性

1.  **视频/音频转字幕 (`qwen3_full_srt.py`)**
    *   支持批量处理大文件。
    *   自动生成 `.srt` 字幕和 `.txt` 纯文本。
    *   支持断点续传（通过 checkpoint 文件）。
    *   GPU 加速推理。

2.  **实时语音转文字 (`qwen3_realtime.py`)**
    *   **实时悬浮窗**：透明置顶窗口，适合直播叠加。
    *   **双模式**：支持麦克风录音和声卡内录（需选择对应设备 ID）。
    *   **低延迟**：实时流式推理，秒级反馈。

## 环境要求

*   Python 3.10+ (推荐 3.12 或 3.14)
*   CUDA 环境 (NVIDIA GPU)
*   依赖库：`transformers`, `torch`, `av`, `sounddevice`, `soundfile`, `numpy`

## 快速使用

### 1. 视频转字幕
```powershell
python qwen3_full_srt.py "你的视频路径.mp4" --batch 12
```

### 2. 实时字幕
查看设备列表：
```powershell
python qwen3_realtime.py --list
```
开启实时字幕（以 ID 1 为例）：
```powershell
python qwen3_realtime.py --device_id 1
```

## 注意事项
*   模型权重默认放置在 `./models/Qwen/Qwen3-ASR-0___6B`。
*   实时模式下，若要使用声卡内录，请在 `--list` 中寻找带有 `Loopback` 或 `立体声混音` 字样的设备 ID。
