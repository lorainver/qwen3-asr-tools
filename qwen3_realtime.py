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
        width, height = 1000, 160
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # 背景和文字样式 (适合 OBS 绿幕或透明采集)
        self.frame = tk.Frame(self.root, bg="#1a1a1a", highlightthickness=2, highlightbackground="#3d3d3d")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = tk.Label(
            self.frame, 
            text="Qwen3-ASR 实时字幕准备中...", 
            font=("Microsoft YaHei", 20, "bold"), 
            fg="#00ff00", 
            bg="#1a1a1a", 
            wraplength=950,
            justify="center",
            pady=10
        )
        self.label.pack(expand=True, pady=10)

        # 右上角关闭按钮
        self.close_button = tk.Label(
            self.frame,
            text=" × ",
            font=("Arial", 16, "bold"),
            fg="#666",
            bg="#1a1a1a",
            cursor="hand2"
        )
        self.close_button.place(relx=1.0, rely=0.0, anchor="ne")
        self.close_button.bind("<Button-1>", lambda e: self.root.destroy())
        self.close_button.bind("<Enter>", lambda e: self.close_button.config(fg="white", bg="red"))
        self.close_button.bind("<Leave>", lambda e: self.close_button.config(fg="#666", bg="#1a1a1a"))

        # 鼠标拖动功能
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)
        
        self.history = ["", ""] # 存储最近两行
        self.is_translating = False # 翻译状态同步
        self.lang_list = [None, "Japanese", "English", "Chinese"]
        self.lang_names = ["Auto", "Ja", "En", "Zh"]
        self.lang_idx = 0
        
        # 语言选择按钮
        self.lang_btn = tk.Label(
            self.frame,
            text=self.lang_names[self.lang_idx],
            font=("Arial", 10, "bold"),
            fg="#aaa",
            bg="#222",
            cursor="hand2",
            padx=5,
            pady=2
        )
        self.lang_btn.place(relx=1.0, rely=1.0, anchor="se", x=-55, y=-10)
        self.lang_btn.bind("<Button-1>", self.cycle_lang)

        # 翻译切换按钮
        self.trans_btn = tk.Label(
            self.frame,
            text=" 原 ",
            font=("Arial", 11, "bold"),
            fg="white",
            bg="#444",
            cursor="hand2",
            padx=5,
            pady=2
        )
        self.trans_btn.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        self.trans_btn.bind("<Button-1>", self.toggle_translate)

    def toggle_translate(self, event):
        self.is_translating = not self.is_translating
        self.trans_btn.config(
            text=" 译 " if self.is_translating else " 原 ", 
            bg="#0078d4" if self.is_translating else "#444"
        )
        # 翻译模式下置灰语言选择
        if self.is_translating:
            self.lang_btn.config(fg="#555", bg="#111")
        else:
            self.lang_btn.config(fg="#aaa", bg="#222")
            
        mode = "翻译" if self.is_translating else "原文"
        print(f"\n >>> 已切换至 [{mode}] 模式")

    def cycle_lang(self, event):
        if self.is_translating: return
        self.lang_idx = (self.lang_idx + 1) % len(self.lang_list)
        self.lang_btn.config(text=self.lang_names[self.lang_idx])
        print(f" >>> 语种锁定: {self.lang_names[self.lang_idx]}")

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
        if text and text != self.history[-1]:
            self.history = [self.history[1], text]
            display_text = f"{self.history[0]}\n{self.history[1]}" if self.history[0] else self.history[1]
            self.label.config(text=display_text)

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
    parser.add_argument("--model_size", default="1.7B", choices=["0.6B", "1.7B"], help="选择模型大小 (0.6B 速度快, 1.7B 精度高)")
    parser.add_argument("--device_id", type=int, default=None, help="指定音频设备ID")
    parser.add_argument("--chunk", type=float, default=2.5, help="录音片段长度(秒)，建议 2-4 秒")
    parser.add_argument("--loopback", action="store_true", help="尝试自动开启声卡内录 (Windows WASAPI)")
    parser.add_argument("--list", action="store_true", help="列出所有音频设备")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    # 适配模型路径
    m_name = "Qwen3-ASR-1___7B" if args.model_size == "1.7B" else "Qwen3-ASR-0___6B"
    model_path = str(Path(args.model_dir) / "Qwen" / m_name)

    # 1. 初始化 GUI
    gui = FloatingCaption()

    # 2. 加载模型
    print(f"正在加载 Qwen3-ASR {args.model_size} 模型 (FP16/CUDA)...")
    from qwen_asr import Qwen3ASRModel
    import transformers
    import torch
    transformers.logging.set_verbosity_error()
    
    # 显存优化配置：强制开启 FP16 半精度加速
    model = Qwen3ASRModel.from_pretrained(
        model_path, 
        device_map='cuda', 
        torch_dtype=torch.float16,
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
                if "Loopback" in dev['name'] or "回放" in dev['name']:
                    print(f"自动选择内录设备: {dev['name']}")
                    target_device = i
                    break

    # 获取设备详细参数以避免 Invalid Sample Rate / Channel 错误
    try:
        dev_info = sd.query_devices(target_device, 'input')
        device_samplerate = int(dev_info['default_samplerate'])
        device_channels = int(dev_info['max_input_channels'])
        print(f"设备参数: ID {target_device} | 采样率 {device_samplerate}Hz | 声道 {device_channels}")
    except Exception as e:
        print(f"获取设备信息失败: {e}")
        return

    def transcription_worker():
        print(f"录音已启动...")
        buffer = []
        # 计算对应设备采样率下的片段长度
        samples_per_chunk = int(device_samplerate * args.chunk)
        
        from scipy.signal import resample

        with sd.InputStream(device=target_device, channels=device_channels, samplerate=device_samplerate, callback=callback):
            while True:
                data = audio_queue.get()
                buffer.append(data)
                
                current_samples = sum(len(b) for b in buffer)
                if current_samples >= samples_per_chunk:
                    chunk = np.concatenate(buffer)
                    buffer = []
                    
                    # 1. 如果是多声道，取平均值转为单声道
                    if device_channels > 1:
                        chunk = np.mean(chunk, axis=1)
                    else:
                        chunk = chunk.flatten()

                    # 2. 静音检测 (防止“嗯”刷屏)
                    max_amplitude = np.abs(chunk).max()
                    # 在后台打印微弱的电平提示，方便调试（可选）
                    # sys.stdout.write(f"\r[当前信号强度: {max_amplitude:.4f}]")
                    # sys.stdout.flush()

                    if max_amplitude < 0.001: # 阈值降低到 0.001
                        continue

                    # 3. 重采样到 16000Hz (Qwen3 必需)
                    if device_samplerate != 16000:
                        num_samples = int(len(chunk) * 16000 / device_samplerate)
                        chunk = resample(chunk, num_samples)
                    
                    # 4. 临时保存用于推理
                    temp_wav = f"rt_chunk_{int(time.time())}.wav"
                    sf.write(temp_wav, chunk, 16000)
                    
                    try:
                        t0 = time.time()
                        # 联动 GUI 的状态
                        if gui.is_translating:
                            context_msg = "Translate to Chinese"
                            target_lang = None
                        else:
                            context_msg = "" # 原文模式下保持纯净
                            target_lang = gui.lang_list[gui.lang_idx]
                            
                        results = model.transcribe(
                            audio=[temp_wav], 
                            context=context_msg, 
                            language=target_lang
                        )
                        dt = time.time() - t0
                        
                        # 定期清理显存
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        
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
