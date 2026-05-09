import sys, time, os, threading, queue, argparse
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import tkinter as tk
from pathlib import Path

# 适配路径
sys.path.append(r"D:\qwen3-asr")

class FloatingCaption:
    """透明悬浮字幕窗口"""
    def __init__(self, title="Qwen3 实速记"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True) # 无边框
        self.root.attributes("-topmost", True) # 置顶
        self.root.attributes("-alpha", 0.8) # 整体透明度
        
        # 窗口大小和位置
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width, height = 1000, 120
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # 背景和文字样式 (适合 OBS 绿幕或透明采集)
        self.frame = tk.Frame(self.root, bg="#1a1a1a", highlightthickness=2, highlightbackground="#3d3d3d")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = tk.Label(
            self.frame, 
            text="Qwen3-ASR 实时字幕准备中...", 
            font=("Microsoft YaHei", 22, "bold"), 
            fg="#00ff00", # 经典的亮绿色
            bg="#1a1a1a", 
            wraplength=950,
            justify="center"
        )
        self.label.pack(expand=True, pady=10)

        # 鼠标拖动功能
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)
        
        self.last_text = ""

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def update_text(self, text):
        if text and text != self.last_text:
            self.label.config(text=text)
            self.last_text = text

    def run(self):
        self.root.mainloop()

def list_devices():
    print("\n可用音频设备列表:")
    print("-" * 60)
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        input_ch = dev['max_input_channels']
        output_ch = dev['max_output_channels']
        api = sd.query_hostapis(dev['hostapi'])['name']
        print(f"ID {i}: {dev['name']} (API: {api}) | 输入: {input_ch}, 输出: {output_ch}")
    print("-" * 60)

def main():
    parser = argparse.ArgumentParser(description="Qwen3-ASR 实时语音转文字 (GUI)")
    parser.add_argument("--model_dir", default=r"D:\qwen3-asr\models")
    parser.add_argument("--device_id", type=int, default=None, help="指定音频设备ID")
    parser.add_argument("--chunk", type=float, default=2.5, help="录音片段长度(秒)，建议 2-4 秒")
    parser.add_argument("--loopback", action="store_true", help="尝试自动开启声卡内录 (Windows WASAPI)")
    parser.add_argument("--list", action="store_true", help="列出所有音频设备")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    model_path = str(Path(args.model_dir) / "Qwen" / "Qwen3-ASR-0___6B")

    # 1. 初始化 GUI
    gui = FloatingCaption()

    # 2. 加载模型
    print("正在加载 Qwen3-ASR 模型 (CUDA)...")
    from qwen_asr import Qwen3ASRModel
    import transformers
    transformers.logging.set_verbosity_error()
    
    # 显存优化配置
    model = Qwen3ASRModel.from_pretrained(
        model_path, 
        device_map='cuda', 
        max_new_tokens=256
    )
    print("模型加载完毕！")

    # 3. 音频处理逻辑
    audio_queue = queue.Queue()
    samplerate = 16000
    channels = 1

    def callback(indata, frames, time_info, status):
        if status:
            print(f"Status: {status}")
        audio_queue.put(indata.copy())

    # 寻找设备
    target_device = args.device_id
    if args.loopback and target_device is None:
        print("正在寻找 Windows WASAPI 循环回放设备 (内录)...")
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if "WASAPI" in sd.query_hostapis(dev['hostapi'])['name'] and dev['max_input_channels'] > 0:
                # 某些驱动会将 Loopback 标记为输入设备
                if "Loopback" in dev['name'] or "回放" in dev['name']:
                    print(f"自动选择内录设备: {dev['name']}")
                    target_device = i
                    break

    def transcription_worker():
        print(f"开始录音，采样率: {samplerate}Hz")
        buffer = []
        samples_per_chunk = int(samplerate * args.chunk)
        
        with sd.InputStream(device=target_device, channels=channels, samplerate=samplerate, callback=callback):
            while True:
                data = audio_queue.get()
                buffer.append(data)
                
                # 积攒足够长度后处理
                current_samples = sum(len(b) for b in buffer)
                if current_samples >= samples_per_chunk:
                    chunk = np.concatenate(buffer)
                    buffer = [] # 清空缓存
                    
                    # 临时保存用于推理
                    temp_wav = f"rt_chunk_{int(time.time())}.wav"
                    sf.write(temp_wav, chunk, samplerate)
                    
                    try:
                        t0 = time.time()
                        results = model.transcribe(audio=[temp_wav], language=None)
                        dt = time.time() - t0
                        
                        if results:
                            res = results[0] if isinstance(results, list) else results
                            text = "".join(str(s.text) for s in (res if hasattr(res, '__iter__') else [res]))
                            text = text.replace("nan", "").replace("np.", "").strip()
                            
                            if text:
                                print(f"[{time.strftime('%H:%M:%S')}] {text} (推理: {dt:.2f}s)")
                                gui.update_text(text)
                    except Exception as e:
                        print(f"推理失败: {e}")
                    finally:
                        if os.path.exists(temp_wav):
                            os.remove(temp_wav)

    # 4. 启动后台线程
    t = threading.Thread(target=transcription_worker, daemon=True)
    t.start()

    # 5. 运行 GUI (主线程)
    print("\n" + "="*50)
    print("  Qwen3-ASR 实时转录已启动！")
    print("  - 鼠标左键可拖动字幕窗")
    print("  - 控制台将同步输出文本")
    print("="*50 + "\n")
    gui.run()

if __name__ == "__main__":
    main()
