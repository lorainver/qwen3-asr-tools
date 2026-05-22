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
    """透明悬浮字幕窗口 — 2026极简科幻磨砂全动画重构版"""
    def __init__(self, title="Qwen3 实速记"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True) # 无边框
        self.root.attributes("-topmost", True) # 置顶
        self.root.attributes("-alpha", 0.85) # 整体透明度 85%
        
        # 窗口大小和位置 (增加一些高度以便容纳多行卡片)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width, height = 1100, 220
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # 精致的黑曜石深邃背景 (Obsidian Dark) 及微蓝渐变描边
        self.frame = tk.Frame(self.root, bg="#090d16", highlightthickness=2, highlightbackground="#1e293b")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # 使用三个独立的 Frame 作为 Line Component 承载三行字幕 (支持 shadow Label 偏置投影)
        self.max_lines = 3
        self.history = [] # 历史存储队列，最近 3 句话
        self.line_frames = []
        self.line_shadows = []
        self.line_mains = []
        
        # 定义三行自适应层级样式 (字号自上而下递增，色彩由暗到明退火)
        # line 0: 历史第3句 (最上行)，最暗最幼。
        # line 1: 历史第2句 (中间行)，次暗次中。
        # line 2: 正在说的话 (最新最底行)，最亮最大。
        self.line_styles = [
            {"font": ("Microsoft YaHei", 14, "bold"), "fg": "#475569", "shadow_fg": "#000000"}, # 历史冷灰
            {"font": ("Microsoft YaHei", 17, "bold"), "fg": "#007700", "shadow_fg": "#000000"}, # 历史暗绿 (退火)
            {"font": ("Microsoft YaHei", 22, "bold"), "fg": "#00ff00", "shadow_fg": "#000000"}  # 最新高亮绿
        ]
        
        # 构建行组件
        for i in range(self.max_lines):
            # 行级独立子容器
            lf = tk.Frame(self.frame, bg="#090d16")
            lf.pack(fill=tk.X, expand=True, padx=25, pady=2)
            self.line_frames.append(lf)
            
            style = self.line_styles[i]
            # 阴影文本层
            shadow_lbl = tk.Label(
                lf, text="", font=style["font"], fg=style["shadow_fg"], bg="#090d16", 
                justify="center", wraplength=1040
            )
            # 巧妙偏置 2 像素以制造立体的 3D 投影效果，自适应高宽
            shadow_lbl.place(x=2, y=2, relwidth=1.0, relheight=1.0)
            self.line_shadows.append(shadow_lbl)
            
            # 主文本层
            main_lbl = tk.Label(
                lf, text="", font=style["font"], fg=style["fg"], bg="#090d16",
                justify="center", wraplength=1040
            )
            main_lbl.pack(fill=tk.BOTH, expand=True)
            self.line_mains.append(main_lbl)
            
        # 右上角关闭按钮 (加入亮红 Hover 反馈)
        self.close_button = tk.Label(
            self.frame, text=" × ", font=("Arial", 16, "bold"), fg="#475569", bg="#090d16", cursor="hand2"
        )
        self.close_button.place(relx=1.0, rely=0.0, anchor="ne")
        self.close_button.bind("<Button-1>", lambda e: self.root.destroy())
        self.close_button.bind("<Enter>", lambda e: self.close_button.config(fg="#f87171", bg="#1f2937"))
        self.close_button.bind("<Leave>", lambda e: self.close_button.config(fg="#475569", bg="#090d16"))

        # 鼠标拖动与拉伸支持
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)
        for shadow in self.line_shadows:
            shadow.bind("<Button-1>", self.start_move)
            shadow.bind("<B1-Motion>", self.do_move)
        for main in self.line_mains:
            main.bind("<Button-1>", self.start_move)
            main.bind("<B1-Motion>", self.do_move)
            
        # 语言支持
        self.lang_list = [None, "Japanese", "English", "Chinese"]
        self.lang_names = ["Auto", "Ja", "En", "Zh"]
        self.lang_idx = 0
        
        # 语言切换按钮 (磨砂精致小卡片)
        self.lang_btn = tk.Label(
            self.frame, text=self.lang_names[self.lang_idx], font=("Arial", 11, "bold"),
            fg="#94a3b8", bg="#1e293b", cursor="hand2", padx=8, pady=4
        )
        self.lang_btn.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-15)
        self.lang_btn.bind("<Button-1>", self.cycle_lang)
        self.lang_btn.bind("<Enter>", lambda e: self.lang_btn.config(fg="white", bg="#3b82f6"))
        self.lang_btn.bind("<Leave>", lambda e: self.lang_btn.config(fg="#94a3b8", bg="#1e293b"))
        
        # 动效状态控制
        self.typewriter_after_id = None
        self.cursor_after_id = None
        self.cursor_state = False
        self.cursor_visible = True
        self.is_typing = False
        
        # 开启倾听呼吸光标慢闪循环
        self._blink_cursor()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        
    def cycle_lang(self, event):
        self.lang_idx = (self.lang_idx + 1) % len(self.lang_list)
        self.lang_btn.config(text=self.lang_names[self.lang_idx])
        print(f" >>> 语种锁定: {self.lang_names[self.lang_idx]}")

    def _blink_cursor(self):
        """光标慢速呼吸慢闪动效 (当系统闲置或未运行打字机时激活)"""
        # 取消之前的 after
        if self.cursor_after_id:
            self.root.after_cancel(self.cursor_after_id)
            self.cursor_after_id = None
            
        if self.cursor_visible and not self.is_typing:
            self.cursor_state = not self.cursor_state
            cursor_char = " ▊" if self.cursor_state else "   "
            
            # 最新的一行 (栈底) 在 text 后面追加呼吸光标
            current_text = self.history[-1] if self.history else "倾听中..."
            self.line_mains[-1].config(text=current_text + cursor_char)
            self.line_shadows[-1].config(text=current_text + cursor_char)
            
        self.cursor_after_id = self.root.after(500, self._blink_cursor)

    def _trigger_typewriter(self, target_text, speed=15, current_idx=1):
        """流式打字机高拟真吐字效果，带光标随行动效"""
        if self.typewriter_after_id:
            self.root.after_cancel(self.typewriter_after_id)
            self.typewriter_after_id = None
            
        # 打字中，光标保持常亮随行
        self.is_typing = True
        self.cursor_visible = False
        
        current_show = target_text[:current_idx]
        text_with_cursor = current_show + " ▊"
        
        self.line_mains[-1].config(text=text_with_cursor)
        self.line_shadows[-1].config(text=text_with_cursor)
        
        if current_idx < len(target_text):
            self.typewriter_after_id = self.root.after(
                speed, lambda: self._trigger_typewriter(target_text, speed, current_idx + 1)
            )
        else:
            # 打字结束，光标退回慢闪状态
            self.is_typing = False
            self.cursor_visible = True
            self.typewriter_after_id = None
            self._blink_cursor()

    def update_text(self, text):
        if not text:
            return
            
        # 去重保护，防止完全相同的数据反复刷新引发闪烁
        if self.history and text == self.history[-1]:
            return
            
        # 加入历史队列
        self.history.append(text)
        if len(self.history) > self.max_lines:
            self.history.pop(0)
            
        # 更新各行的显示内容
        n_history = len(self.history)
        
        # 1. 刷新历史老行 (不带打字机，直接渲染并自适应退火变暗)
        for i in range(self.max_lines - 1):
            # 将历史映射到对应行：如果历史不够 max_lines 行，则可能有些行是空的
            history_idx = n_history - 1 - (self.max_lines - 1 - i)
            if history_idx >= 0 and history_idx < n_history - 1:
                hist_text = self.history[history_idx]
                self.line_mains[i].config(text=hist_text)
                self.line_shadows[i].config(text=hist_text)
            else:
                self.line_mains[i].config(text="")
                self.line_shadows[i].config(text="")
                
        # 2. 刷新最新说的一句话 (最底下一行)：触发打字机渐显与常亮光标
        latest_text = self.history[-1]
        self._trigger_typewriter(latest_text)

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

    # 2. 加载模型 (自适应硬件半精度加速：RTX 5060 自动启用原生 bfloat16)
    import torch
    if torch.cuda.is_available():
        device_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        device_dtype = torch.float32
        
    print(f"正在加载 Qwen3-ASR {args.model_size} 模型 ({device_dtype}/CUDA)...")
    from qwen_asr import Qwen3ASRModel
    import transformers
    transformers.logging.set_verbosity_error()
    
    model = Qwen3ASRModel.from_pretrained(
        model_path, 
        device_map='cuda', 
        torch_dtype=device_dtype,
        dtype=device_dtype,
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

                    if max_amplitude < 0.001: # 阈值降低到 0.001
                        continue

                    # 3. 重采样到 16000Hz (Qwen3 必需)
                    if device_samplerate != 16000:
                        num_samples = int(len(chunk) * 16000 / device_samplerate)
                        chunk = resample(chunk, num_samples)
                    
                    try:
                        t0 = time.time()
                        target_lang = gui.lang_list[gui.lang_idx]
                            
                        # 核心重构：零磁盘 IO，内存直接传输 NumPy 数组给 ASR 引擎推理
                        # 格式支持: (np.ndarray, samplerate)
                        results = model.transcribe(
                            audio=[(chunk, 16000)], 
                            context="", 
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
