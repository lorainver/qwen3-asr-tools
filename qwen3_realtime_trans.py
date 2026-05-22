import sys, time, os, threading, queue, argparse
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import tkinter as tk
import requests
import json
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import transformers
import warnings

# 屏蔽所有冗余警告
transformers.logging.set_verbosity_error()
warnings.filterwarnings("ignore")
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["BITSANDBYTES_NOWELCOME"] = "1"

# 适配路径
sys.path.append(r"D:\qwen3-asr")

class FloatingCaption:
    """透明悬浮字幕窗口 — 双语同传科幻磨砂全动画重构版"""
    def __init__(self, title="Qwen3 实时同声传译"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True) # 无边框
        self.root.attributes("-topmost", True) # 置顶
        self.root.attributes("-alpha", 0.85) # 整体透明度 85%
        
        # 窗口大小和位置 (240 像素高度为多行双语堆栈提供充足空间)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width, height = 1100, 240
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # 精致的黑曜石深邃背景 (Obsidian Dark) 及科技蓝描边
        self.frame = tk.Frame(self.root, bg="#090d16", highlightthickness=2, highlightbackground="#0078d4")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # 存储历史队列
        self.raw_history = []    # 原文历史
        self.trans_history = []  # 译文历史
        
        # 模式与行数状态
        self.display_mode = 0  # 0: 双语, 1: 仅原文, 2: 仅译文
        self.mode_names = ["双", "原", "译"]
        self.max_display_lines = 2  # 默认显示 2 行，极致饱满
        
        # 语言支持
        self.lang_list = [None, "Japanese", "English", "Chinese"]
        self.lang_names = ["Auto", "Ja", "En", "Zh"]
        self.lang_idx = 1  # 默认日文
        
        # 定义三行自适应层级样式 (字号自上而下递增，色彩由暗到明退火)
        self.raw_styles = [
            {"font": ("Microsoft YaHei", 13, "bold"), "fg": "#475569", "shadow_fg": "#000000"}, # 历史冷灰
            {"font": ("Microsoft YaHei", 16, "bold"), "fg": "#006600", "shadow_fg": "#000000"}, # 历史暗绿
            {"font": ("Microsoft YaHei", 20, "bold"), "fg": "#00ff00", "shadow_fg": "#000000"}  # 最新高亮绿
        ]
        self.trans_styles = [
            {"font": ("Microsoft YaHei", 14, "bold"), "fg": "#475569", "shadow_fg": "#000000"}, # 历史冷灰
            {"font": ("Microsoft YaHei", 17, "bold"), "fg": "#007777", "shadow_fg": "#000000"}, # 历史暗青
            {"font": ("Microsoft YaHei", 21, "bold"), "fg": "#00ffff", "shadow_fg": "#000000"}  # 最新高亮天蓝
        ]
        
        # 创建两个独立的 Container 分别容纳原文和译文行组件
        self.raw_container = tk.Frame(self.frame, bg="#090d16")
        self.trans_container = tk.Frame(self.frame, bg="#090d16")
        
        # 原文行组件 (最多3行)
        self.raw_frames = []
        self.raw_shadows = []
        self.raw_mains = []
        
        # 译文行组件 (最多3行)
        self.trans_frames = []
        self.trans_shadows = []
        self.trans_mains = []
        
        # 构建原文行
        for i in range(3):
            lf = tk.Frame(self.raw_container, bg="#090d16")
            self.raw_frames.append(lf)
            style = self.raw_styles[i]
            
            shadow_lbl = tk.Label(lf, text="", font=style["font"], fg=style["shadow_fg"], bg="#090d16", justify="center", wraplength=1040)
            shadow_lbl.place(x=2, y=2, relwidth=1.0, relheight=1.0)
            self.raw_shadows.append(shadow_lbl)
            
            main_lbl = tk.Label(lf, text="", font=style["font"], fg=style["fg"], bg="#090d16", justify="center", wraplength=1040)
            main_lbl.pack(fill=tk.BOTH, expand=True)
            self.raw_mains.append(main_lbl)
            
        # 构建译文行
        for i in range(3):
            lf = tk.Frame(self.trans_container, bg="#090d16")
            self.trans_frames.append(lf)
            style = self.trans_styles[i]
            
            shadow_lbl = tk.Label(lf, text="", font=style["font"], fg=style["shadow_fg"], bg="#090d16", justify="center", wraplength=1040)
            shadow_lbl.place(x=2, y=2, relwidth=1.0, relheight=1.0)
            self.trans_shadows.append(shadow_lbl)
            
            main_lbl = tk.Label(lf, text="", font=style["font"], fg=style["fg"], bg="#090d16", justify="center", wraplength=1040)
            main_lbl.pack(fill=tk.BOTH, expand=True)
            self.trans_mains.append(main_lbl)
            
        # 右上角关闭按钮 (加入红 Hover 反馈)
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
        
        # 统一绑定拖动事件
        def bind_drag(widget):
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)
            
        for shadows in [self.raw_shadows, self.trans_shadows]:
            for s in shadows: bind_drag(s)
        for mains in [self.raw_mains, self.trans_mains]:
            for m in mains: bind_drag(m)
            
        # 按钮容器
        self.btn_frame = tk.Frame(self.frame, bg="#1e293b")
        self.btn_frame.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-15)
        
        # 语言选择按钮 (磨砂精致小卡片)
        self.lang_btn = tk.Label(
            self.btn_frame, text=self.lang_names[self.lang_idx], font=("Arial", 10, "bold"),
            fg="#94a3b8", bg="#1e293b", cursor="hand2", padx=8, pady=3
        )
        self.lang_btn.pack(side=tk.LEFT, padx=2)
        self.lang_btn.bind("<Button-1>", self.cycle_lang)
        self.lang_btn.bind("<Enter>", lambda e: self.lang_btn.config(fg="white", bg="#3b82f6"))
        self.lang_btn.bind("<Leave>", lambda e: self.lang_btn.config(fg="#94a3b8", bg="#1e293b"))
        
        # 模式切换按钮
        self.mode_btn = tk.Label(
            self.btn_frame, text=self.mode_names[self.display_mode], font=("Arial", 10, "bold"),
            fg="white", bg="#0078d4", cursor="hand2", padx=8, pady=3
        )
        self.mode_btn.pack(side=tk.LEFT, padx=2)
        self.mode_btn.bind("<Button-1>", self.cycle_mode)
        
        # 行数切换按钮
        self.line_btn = tk.Label(
            self.btn_frame, text=f"{self.max_display_lines}L", font=("Arial", 10, "bold"),
            fg="#eee", bg="#475569", cursor="hand2", padx=8, pady=3
        )
        self.line_btn.pack(side=tk.LEFT, padx=2)
        self.line_btn.bind("<Button-1>", self.cycle_lines)
        
        # 窗口大小微调拉伸按钮
        self.resizer = tk.Label(self.btn_frame, text="◢", font=("Arial", 10), fg="#64748b", bg="#1e293b", cursor="size_nw_se")
        self.resizer.pack(side=tk.LEFT, padx=(5, 0))
        self.resizer.bind("<Button-1>", self.start_resize)
        self.resizer.bind("<B1-Motion>", self.do_resize)
        
        self.root.bind("<Configure>", self.on_window_resize)
        
        # 独立的打字机与光标动画控制变量
        self.raw_typewriter_after_id = None
        self.raw_cursor_after_id = None
        self.raw_cursor_state = False
        self.raw_cursor_visible = True
        self.raw_is_typing = False
        
        self.trans_typewriter_after_id = None
        self.trans_cursor_after_id = None
        self.trans_cursor_state = False
        self.trans_cursor_visible = True
        self.trans_is_typing = False
        
        # 线程安全 UI 调度队列
        self.ui_queue = queue.Queue()
        self._process_ui_queue()

        # 初始化界面布局
        self.refresh_display()
        
        # 开启原文与译文的倾听光标慢闪循环
        self._blink_cursor_raw()
        self._blink_cursor_trans()

    def _process_ui_queue(self):
        """主线程轮询，消费来自后台线程的 GUI 更新任务"""
        try:
            while True:
                task = self.ui_queue.get_nowait()
                action = task.get("action")
                if action == "update_raw":
                    self._do_update_raw(task["text"])
                elif action == "update_trans":
                    self._do_update_trans(task["text"])
                self.ui_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(50, self._process_ui_queue)

    def on_window_resize(self, event):
        """窗口大小变化时，自动调整文字换行宽度"""
        new_width = self.root.winfo_width()
        for i in range(3):
            self.raw_mains[i].config(wraplength=new_width - 60)
            self.raw_shadows[i].config(wraplength=new_width - 60)
            self.trans_mains[i].config(wraplength=new_width - 60)
            self.trans_shadows[i].config(wraplength=new_width - 60)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        
    def start_resize(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.start_width = self.root.winfo_width()
        self.start_height = self.root.winfo_height()

    def do_resize(self, event):
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        new_w = max(400, self.start_width + dx)
        new_h = max(100, self.start_height + dy)
        self.root.geometry(f"{new_w}x{new_h}")

    def cycle_lang(self, event):
        self.lang_idx = (self.lang_idx + 1) % len(self.lang_list)
        self.lang_btn.config(text=self.lang_names[self.lang_idx])
        print(f" >>> 语种锁定: {self.lang_names[self.lang_idx]}")

    def cycle_lines(self, event):
        self.max_display_lines = (self.max_display_lines % 3) + 1
        self.line_btn.config(text=f"{self.max_display_lines}L")
        self.refresh_display()
        print(f" >>> 显示行数: {self.max_display_lines}")

    def cycle_mode(self, event):
        self.display_mode = (self.display_mode + 1) % 3
        self.mode_btn.config(text=self.mode_names[self.display_mode])
        self.refresh_display()
        print(f" >>> 显示模式: {self.mode_names[self.display_mode]}")

    def refresh_display(self):
        """根据当前模式和行数强制刷新显示内容"""
        # 1. 切换容器的显隐
        if self.display_mode == 1: # 仅原文
            self.trans_container.pack_forget()
            self.raw_container.pack(fill=tk.BOTH, expand=True, pady=10)
        elif self.display_mode == 2: # 仅译文
            self.raw_container.pack_forget()
            self.trans_container.pack(fill=tk.BOTH, expand=True, pady=10)
        else: # 双语
            self.raw_container.pack_forget()
            self.trans_container.pack_forget()
            self.raw_container.pack(fill=tk.BOTH, expand=True, pady=(10, 2))
            self.trans_container.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        # 2. 根据最大显示行数重新 pack 原文行与译文行
        for i in range(3):
            self.raw_frames[i].pack_forget()
            self.trans_frames[i].pack_forget()

        # 计算应该展示的行索引范围
        start_idx = 3 - self.max_display_lines
        for i in range(start_idx, 3):
            self.raw_frames[i].pack(fill=tk.X, expand=True, padx=25, pady=2)
            self.trans_frames[i].pack(fill=tk.X, expand=True, padx=25, pady=2)

        # 3. 强制刷新文字
        self.update_raw("")
        self.update_trans("")

    def _blink_cursor_raw(self):
        """原文光标慢速呼吸慢闪动效"""
        if self.raw_cursor_after_id:
            self.root.after_cancel(self.raw_cursor_after_id)
            self.raw_cursor_after_id = None
            
        if self.raw_cursor_visible and not self.raw_is_typing:
            self.raw_cursor_state = not self.raw_cursor_state
            cursor_char = " ▊" if self.raw_cursor_state else "   "
            current_text = self.raw_history[-1] if self.raw_history else "等待识别..."
            if self.display_mode != 2:
                self.raw_mains[2].config(text=current_text + cursor_char)
                self.raw_shadows[2].config(text=current_text + cursor_char)
            
        self.raw_cursor_after_id = self.root.after(500, self._blink_cursor_raw)

    def _blink_cursor_trans(self):
        """译文光标慢速呼吸慢闪动效"""
        if self.trans_cursor_after_id:
            self.root.after_cancel(self.trans_cursor_after_id)
            self.trans_cursor_after_id = None
            
        if self.trans_cursor_visible and not self.trans_is_typing:
            self.trans_cursor_state = not self.trans_cursor_state
            cursor_char = " ▊" if self.trans_cursor_state else "   "
            current_text = self.trans_history[-1] if self.trans_history else "等待翻译..."
            if self.display_mode != 1:
                self.trans_mains[2].config(text=current_text + cursor_char)
                self.trans_shadows[2].config(text=current_text + cursor_char)
            
        self.trans_cursor_after_id = self.root.after(500, self._blink_cursor_trans)

    def _trigger_typewriter_raw(self, target_text, speed=15, current_idx=1):
        """原文流式打字机高拟真吐字"""
        if self.raw_typewriter_after_id:
            self.root.after_cancel(self.raw_typewriter_after_id)
            self.raw_typewriter_after_id = None
            
        self.raw_is_typing = True
        self.raw_cursor_visible = False
        
        current_show = target_text[:current_idx]
        text_with_cursor = current_show + " ▊"
        
        self.raw_mains[2].config(text=text_with_cursor)
        self.raw_shadows[2].config(text=text_with_cursor)
        
        if current_idx < len(target_text):
            self.raw_typewriter_after_id = self.root.after(
                speed, lambda: self._trigger_typewriter_raw(target_text, speed, current_idx + 1)
            )
        else:
            self.raw_is_typing = False
            self.raw_cursor_visible = True
            self.raw_typewriter_after_id = None
            self._blink_cursor_raw()

    def _trigger_typewriter_trans(self, target_text, speed=15, current_idx=1):
        """译文流式打字机高拟真吐字"""
        if self.trans_typewriter_after_id:
            self.root.after_cancel(self.trans_typewriter_after_id)
            self.trans_typewriter_after_id = None
            
        self.trans_is_typing = True
        self.trans_cursor_visible = False
        
        current_show = target_text[:current_idx]
        text_with_cursor = current_show + " ▊"
        
        self.trans_mains[2].config(text=text_with_cursor)
        self.trans_shadows[2].config(text=text_with_cursor)
        
        if current_idx < len(target_text):
            self.trans_typewriter_after_id = self.root.after(
                speed, lambda: self._trigger_typewriter_trans(target_text, speed, current_idx + 1)
            )
        else:
            self.trans_is_typing = False
            self.trans_cursor_visible = True
            self.trans_typewriter_after_id = None
            self._blink_cursor_trans()

    def update_raw(self, text):
        self.ui_queue.put({"action": "update_raw", "text": text})

    def update_trans(self, text):
        self.ui_queue.put({"action": "update_trans", "text": text})

    def _do_update_raw(self, text):
        if text:
            if self.raw_history and text == self.raw_history[-1]:
                return
            self.raw_history.append(text)
            if len(self.raw_history) > self.max_display_lines:
                self.raw_history.pop(0)

        n_history = len(self.raw_history)
        # 1. 刷新历史行（不带打字机，直接渲染自适应退火变暗）
        for i in range(3 - self.max_display_lines, 2):
            history_idx = n_history - 1 - (2 - i)
            if history_idx >= 0 and history_idx < n_history - 1:
                hist_text = self.raw_history[history_idx]
                self.raw_mains[i].config(text=hist_text)
                self.raw_shadows[i].config(text=hist_text)
            else:
                self.raw_mains[i].config(text="")
                self.raw_shadows[i].config(text="")

        # 2. 刷新最新说的一句话 (栈底最后一行 i=2)：触发打字机渐显与常亮光标
        if n_history > 0:
            latest_text = self.raw_history[-1]
            if text:
                self._trigger_typewriter_raw(latest_text)
            else:
                self.raw_mains[2].config(text=latest_text)
                self.raw_shadows[2].config(text=latest_text)
        else:
            self.raw_mains[2].config(text="等待识别..." if self.display_mode != 2 else "")
            self.raw_shadows[2].config(text="等待识别..." if self.display_mode != 2 else "")

    def _do_update_trans(self, text):
        if text:
            if self.trans_history and text == self.trans_history[-1]:
                return
            self.trans_history.append(text)
            if len(self.trans_history) > self.max_display_lines:
                self.trans_history.pop(0)

        n_history = len(self.trans_history)
        # 1. 刷新历史老行
        for i in range(3 - self.max_display_lines, 2):
            history_idx = n_history - 1 - (2 - i)
            if history_idx >= 0 and history_idx < n_history - 1:
                hist_text = self.trans_history[history_idx]
                self.trans_mains[i].config(text=hist_text)
                self.trans_shadows[i].config(text=hist_text)
            else:
                self.trans_mains[i].config(text="")
                self.trans_shadows[i].config(text="")

        # 2. 刷新最新的一句
        if n_history > 0:
            latest_text = self.trans_history[-1]
            if text:
                self._trigger_typewriter_trans(latest_text)
            else:
                self.trans_mains[2].config(text=latest_text)
                self.trans_shadows[2].config(text=latest_text)
        else:
            self.trans_mains[2].config(text="等待翻译..." if self.display_mode != 1 else "")
            self.trans_shadows[2].config(text="等待翻译..." if self.display_mode != 1 else "")

    def run(self):
        self.root.mainloop()

class OllamaTranslator:
    """Ollama API 翻译器 (利用本地 7B 或其他大模型)"""
    def __init__(self, model_id="qwen2.5:3b", url="http://localhost:11434/v1/chat/completions"):
        self.model_id = model_id
        self.url = url
        # 强制禁用代理
        self.session = requests.Session()
        self.session.trust_env = False
        print(f"初始化 Ollama 翻译器: {model_id} via {url}")

    def translate(self, text, history=""):
        if not text: return ""
        
        # 1. 构造多角色消息流，强制锁定“工具”人格
        # 极大精简 System Prompt 并去除随动 history，以 100% 激活 Ollama 的 Prompt Cache 机制
        messages = [
            {
                "role": "system", 
                "content": "你是一个专业的同传翻译机。请直接将文本翻译为中文，不要输出任何多余内容。"
            },
            {
                "role": "user", 
                "content": text
            }
        ]
        
        try:
            payload = {
                "model": self.model_id,
                "messages": messages,
                "stream": False,
                "temperature": 0.1, # 极低随机性
                "options": {
                    "num_predict": 48, # 同传单句极短，48 足够，能大幅剪枝生成耗时
                    "stop": ["Note:", "注：", "Translation:", "原文：", "\n\n"] # 遇到解释标志立刻停止
                }
            }
            response = self.session.post(self.url, json=payload, timeout=60)
            if response.status_code == 200:
                raw_res = response.json()['choices'][0]['message']['content'].strip()
                for s in ["Note:", "注：", "Translation:"]:
                    if s in raw_res: raw_res = raw_res.split(s)[0].strip()
                return raw_res
            else:
                return f"[API Error {response.status_code}]"
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                return f"[Ollama Timeout]"
            return f"[Ollama Error: {error_msg}]"

class LocalTranslator:
    """本地 LLM 翻译器 (GPU 4-bit 闪电级极速推理)"""
    def __init__(self, model_path):
        print("正在加载本地翻译模型 (运行于 CUDA / GPU 4-bit)...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            
        self.device = "cuda"
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4"
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map="auto"
        )
        print("本地翻译模型加载完毕！(设备: CUDA 4-bit)")

    def translate(self, text, history=""):
        if not text: return ""
        
        # 极简双角色 Prompt，强力激活 Prompt Cache 并彻底杜绝多余解释/话痨幻觉
        messages = [
            {"role": "system", "content": "你是一个专业的同传翻译机。请直接将文本翻译为中文，不要输出任何多余内容。"},
            {"role": "user", "content": text}
        ]
        
        input_ids = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=True, 
            add_generation_prompt=True, 
            return_tensors="pt"
        ).to(self.device)
        
        gen_config = {
            "max_new_tokens": 48, # 限制同传单句翻译的生成长度
            "do_sample": False,
            "pad_token_id": self.tokenizer.pad_token_id
        }
        
        with torch.no_grad():
            output_ids = self.model.generate(input_ids, **gen_config)
        
        # 仅截取新生成的翻译内容
        response = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)
        return response.strip()

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
    parser = argparse.ArgumentParser(description="Qwen3 高级实时同传系统")
    parser.add_argument("--device_id", type=int, default=None, help="音频设备 ID")
    parser.add_argument("--chunk", type=float, default=2.5, help="音频分块时长(秒)")
    parser.add_argument("--model_type", type=str, default="1.5b", choices=["1.5b", "3b", "ollama"], help="翻译引擎类型")
    parser.add_argument("--ollama_model", type=str, default="qwen2.5:3b", help="Ollama 模型 ID")
    parser.add_argument("--model_size", type=str, default="1.7B", choices=["0.6B", "1.7B"], help="ASR 模型版本")
    parser.add_argument("--loopback", action="store_true", help="尝试自动开启声卡内录 (Windows WASAPI)")
    parser.add_argument("--list", action="store_true", help="列出所有音频设备")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    # 1. 初始化 GUI
    gui = FloatingCaption()

    # 2. 根据参数加载 ASR 模型 (自适应硬件半精度加速：RTX 5060 自动启用原生 bfloat16)
    from qwen_asr import Qwen3ASRModel
    import torch
    if torch.cuda.is_available():
        device_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        device_dtype = torch.float32

    asr_folder = "Qwen3-ASR-1___7B" if args.model_size == "1.7B" else "Qwen3-ASR-0___6B"
    asr_path = os.path.join(r"D:\qwen3-asr\models\Qwen", asr_folder)
    
    print(f"正在加载 ASR 模型 ({args.model_size}) ({device_dtype}/CUDA)...")
    if not os.path.exists(asr_path):
        print(f"错误: 找不到 ASR 模型路径 {asr_path}")
        sys.exit(1)
        
    asr_model = Qwen3ASRModel.from_pretrained(
        asr_path, 
        device_map='cuda', 
        torch_dtype=device_dtype,
        dtype=device_dtype,
        max_new_tokens=256
    )
    print("ASR 模型加载完毕！")
    
    # 3. 根据参数加载 翻译 引擎
    if args.model_type == "ollama":
        translator = OllamaTranslator(model_id=args.ollama_model)
    else:
        model_name = "Qwen2.5-1.5B-Instruct" if args.model_type == "1.5b" else "Qwen2.5-3B-Instruct"
        trans_path = os.path.join(r"D:\qwen3-asr\models\Qwen", model_name)
        if not os.path.exists(trans_path):
            print(f"错误: 找不到模型路径 {trans_path}")
            sys.exit(1)
        translator = LocalTranslator(trans_path)

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

    # 音频队列和处理
    audio_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        audio_queue.put(indata.copy())

    def worker():
        print("录音同传系统已启动...")
        buffer = []
        trans_history = [] # 存储最近几句识别结果作为上下文
        samples_per_chunk = int(device_samplerate * args.chunk)
        from scipy.signal import resample
        from concurrent.futures import ThreadPoolExecutor

        # 创建一个异步翻译线程池 (2个worker保证多任务不重叠)
        executor = ThreadPoolExecutor(max_workers=2)

        def async_translate(raw_text, context_str):
            try:
                t_start = time.time()
                cn_text = translator.translate(raw_text, history=context_str)
                print(f"译: {cn_text} (耗时: {time.time()-t_start:.2f}s)")
                # 回调 GUI 更新译文
                gui.update_trans(cn_text)
            except Exception as e:
                print(f"翻译失败: {e}")

        with sd.InputStream(device=target_device, channels=device_channels, samplerate=device_samplerate, callback=callback):
            while True:
                data = audio_queue.get()
                buffer.append(data)
                if sum(len(b) for b in buffer) >= samples_per_chunk:
                    chunk = np.concatenate(buffer)
                    buffer = []
                    if device_channels > 1: 
                        chunk = np.mean(chunk, axis=1)
                    else: 
                        chunk = chunk.flatten()
                    
                    if np.abs(chunk).max() < 0.001: 
                        continue

                    if device_samplerate != 16000:
                        num_samples = int(len(chunk) * 16000 / device_samplerate)
                        chunk = resample(chunk, num_samples)
                    
                    try:
                        t0 = time.time()
                        target_lang = gui.lang_list[gui.lang_idx]
                        
                        # 核心重构：零磁盘 IO，内存直接传输 NumPy 数组给 ASR 引擎推理
                        results = asr_model.transcribe(
                            audio=[(chunk, 16000)], 
                            context="", 
                            language=target_lang
                        )
                        dt = time.time() - t0
                        
                        if results:
                            res = results[0] if isinstance(results, list) else results
                            raw_text = "".join(str(s.text) for s in (res if hasattr(res, '__iter__') else [res])).strip()
                            raw_text = raw_text.replace("nan", "").replace("np.", "").strip()
                            
                            if raw_text:
                                print(f"[{time.strftime('%H:%M:%S')}] 原: {raw_text} (ASR: {dt:.2f}s)")
                                # 原文瞬间上屏渲染打字机
                                gui.update_raw(raw_text)
                                
                                # 只有在双语或仅译文模式下才翻译
                                if gui.display_mode != 1:
                                    # 彻底解耦上下文，采用单句直译模式以 100% 命中 Ollama 提示词缓存
                                    context_str = ""
                                    
                                    # 异步提交翻译任务到线程池，绝不阻塞 ASR 录音线程
                                    executor.submit(async_translate, raw_text, context_str)
                                    
                                    # 更新上下文历史
                                    trans_history.append(raw_text)
                                    if len(trans_history) > 10: 
                                        trans_history.pop(0)
                                else:
                                    gui.update_trans("") # 清空译文行
                                
                        if torch.cuda.is_available(): 
                            torch.cuda.empty_cache()
                    except Exception as e: 
                        print(f"Error: {e}")

    # 启动后台线程
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    print("\n" + "="*50)
    print("  Qwen3 实时同声传译 (混合引擎) 已启动！")
    print("  - 鼠标左键可拖动字幕窗")
    print("  - 控制台将同步输出原文与译文")
    print("="*50 + "\n")
    
    gui.run()

if __name__ == "__main__":
    main()
