import sys, time, os, threading, queue, argparse
import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import tkinter as tk
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
    """双行显示：原声 + 翻译"""
    def __init__(self, title="Qwen3 高级实时同传"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        
        width, height = 1100, 180
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        self.frame = tk.Frame(self.root, bg="#1a1a1a", highlightthickness=2, highlightbackground="#0078d4")
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # 原文显示区域 (3个 Label 实现滚动和淡化)
        self.raw_frame = tk.Frame(self.frame, bg="#1a1a1a")
        self.raw_frame.pack(expand=True, fill=tk.X, pady=(5, 0))
        self.raw_labels = []
        self.raw_colors = ["#444444", "#008800", "#00ff00"] # 旧 -> 新 的颜色梯度
        for i in range(3):
            lbl = tk.Label(self.raw_frame, text="", font=("Microsoft YaHei", 18, "bold"),
                         fg=self.raw_colors[i], bg="#1a1a1a", wraplength=1050)
            lbl.pack(fill=tk.X)
            self.raw_labels.append(lbl)
        
        # 翻译显示区域 (3个 Label)
        self.trans_frame = tk.Frame(self.frame, bg="#1a1a1a")
        self.trans_frame.pack(expand=True, fill=tk.X, pady=(0, 5))
        self.trans_labels = []
        self.trans_colors = ["#444444", "#00aaaa", "#00ffff"] # 旧 -> 新
        for i in range(3):
            lbl = tk.Label(self.trans_frame, text="", font=("Microsoft YaHei", 20, "bold"),
                         fg=self.trans_colors[i], bg="#1a1a1a", wraplength=1050)
            lbl.pack(fill=tk.X)
            self.trans_labels.append(lbl)

        # 关闭按钮
        self.close_btn = tk.Label(self.frame, text=" × ", font=("Arial", 14), fg="#555", bg="#1a1a1a", cursor="hand2")
        self.close_btn.place(relx=1.0, rely=0.0, anchor="ne")
        self.close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)
        # 绑定拖动到所有标签
        for lbl in self.raw_labels + self.trans_labels:
            lbl.bind("<Button-1>", self.start_move)
            lbl.bind("<B1-Motion>", self.do_move)
        
        # 模式状态
        self.display_mode = 0
        self.mode_names = ["双", "原", "译"]
        self.max_display_lines = 1 # 默认显示行数
        
        self.raw_history_list = [] # 存储原文历史
        self.trans_history_list = [] # 存储译文历史
        
        # 语种选择
        self.lang_list = [None, "Japanese", "English", "Chinese"]
        self.lang_names = ["Auto", "Ja", "En", "Zh"]
        self.lang_idx = 1 # 默认日文
        
        # 按钮容器
        self.btn_frame = tk.Frame(self.frame, bg="#222")
        self.btn_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        # 语言选择按钮
        self.lang_btn = tk.Label(self.btn_frame, text=self.lang_names[self.lang_idx], font=("Arial", 10, "bold"),
                               fg="#aaa", bg="#222", cursor="hand2", padx=8, pady=2)
        self.lang_btn.pack(side=tk.LEFT, padx=2)
        self.lang_btn.bind("<Button-1>", self.cycle_lang)

        # 模式切换按钮
        self.mode_btn = tk.Label(self.btn_frame, text=self.mode_names[self.display_mode], font=("Arial", 10, "bold"),
                               fg="white", bg="#0078d4", cursor="hand2", padx=8, pady=2)
        self.mode_btn.pack(side=tk.LEFT, padx=2)
        self.mode_btn.bind("<Button-1>", self.cycle_mode)

        # 行数切换按钮
        self.line_btn = tk.Label(self.btn_frame, text=f"{self.max_display_lines}L", font=("Arial", 10, "bold"),
                               fg="#eee", bg="#444", cursor="hand2", padx=8, pady=2)
        self.line_btn.pack(side=tk.LEFT, padx=2)
        self.line_btn.bind("<Button-1>", self.cycle_lines)

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
        # 控制 Frame 显隐
        if self.display_mode == 1: # 仅原文
            self.trans_frame.pack_forget()
            self.raw_frame.pack(expand=True, fill=tk.BOTH)
        elif self.display_mode == 2: # 仅译文
            self.raw_frame.pack_forget()
            self.trans_frame.pack(expand=True, fill=tk.BOTH)
        else: # 双语
            self.raw_frame.pack_forget()
            self.trans_frame.pack_forget()
            self.raw_frame.pack(expand=True, fill=tk.X, pady=(5, 0))
            self.trans_frame.pack(expand=True, fill=tk.X, pady=(0, 5))
        
        # 控制 Label 显隐 (根据 max_display_lines)
        for i in range(3):
            # 只有最后 N 个 label 显示
            show = (i >= (3 - self.max_display_lines))
            if show:
                self.raw_labels[i].pack(fill=tk.X)
                self.trans_labels[i].pack(fill=tk.X)
            else:
                self.raw_labels[i].pack_forget()
                self.trans_labels[i].pack_forget()

        self.update_raw("") 
        self.update_trans("")

    def cycle_lang(self, event):
        self.lang_idx = (self.lang_idx + 1) % len(self.lang_list)
        self.lang_btn.config(text=self.lang_names[self.lang_idx])
        print(f" >>> 语种锁定: {self.lang_names[self.lang_idx]}")

    def start_move(self, event):
        self.x, self.y = event.x, event.y

    def do_move(self, event):
        x = self.root.winfo_x() + event.x - self.x
        y = self.root.winfo_y() + event.y - self.y
        self.root.geometry(f"+{x}+{y}")

    def update_raw(self, text):
        if text:
            self.raw_history_list.append(text)
            if len(self.raw_history_list) > 3: self.raw_history_list.pop(0)
        
        # 将历史记录分配给 3 个 Label
        history = self.raw_history_list
        for i in range(3):
            # 这里的逻辑是：最新的永远在 raw_labels[2]
            # 索引换算：history[-1] -> labels[2], history[-2] -> labels[1]...
            idx_in_hist = len(history) - (3 - i)
            val = history[idx_in_hist] if idx_in_hist >= 0 else ""
            self.raw_labels[i].config(text=val if self.display_mode != 2 else "")

    def update_trans(self, text):
        if text:
            self.trans_history_list.append(text)
            if len(self.trans_history_list) > 3: self.trans_history_list.pop(0)
            
        history = self.trans_history_list
        for i in range(3):
            idx_in_hist = len(history) - (3 - i)
            val = history[idx_in_hist] if idx_in_hist >= 0 else ""
            self.trans_labels[i].config(text=val if self.display_mode != 1 else "")

    def run(self):
        self.root.mainloop()

class LocalTranslator:
    """本地 LLM 翻译器 (4-bit 量化)"""
    def __init__(self, model_path):
        print(f"正在加载翻译模型 (4-bit)...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
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
        print("翻译模型加载完毕！")

    def translate(self, text, history=""):
        if not text: return ""
        # 构造带上下文的 Prompt
        if history:
            prompt = f"上下文：{history}\n请结合上下文，将以下新内容翻译成中文（只输出译文）：\n{text}"
        else:
            prompt = f"请将以下内容直接翻译成中文（只输出译文）：\n{text}"
        
        messages = [{"role": "user", "content": prompt}]
        input_ids = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
        
        # 屏蔽 pad_token_id 警告
        gen_config = {
            "max_new_tokens": 128,
            "do_sample": False,
            "pad_token_id": self.tokenizer.eos_token_id
        }
        
        with torch.no_grad():
            output_ids = self.model.generate(input_ids, **gen_config)
        
        response = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)
        return response.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device_id", type=int, default=30)
    parser.add_argument("--chunk", type=float, default=2.5)
    args = parser.parse_args()

    # 1. 初始化 GUI
    gui = FloatingCaption()

    # 2. 加载 ASR 模型
    from qwen_asr import Qwen3ASRModel
    asr_path = r"D:\qwen3-asr\models\Qwen\Qwen3-ASR-1___7B"
    print(f"正在加载 ASR 模型 (FP16)...")
    asr_model = Qwen3ASRModel.from_pretrained(asr_path, device_map='cuda', torch_dtype=torch.float16)
    
    # 3. 加载 翻译 模型
    trans_path = r"D:\qwen3-asr\models\Qwen\Qwen2.5-1.5B-Instruct"
    translator = LocalTranslator(trans_path)

    # 音频队列和处理
    audio_queue = queue.Queue()
    dev_info = sd.query_devices(args.device_id, 'input')
    samplerate = int(dev_info['default_samplerate'])
    channels = int(dev_info['max_input_channels'])

    def callback(indata, frames, time_info, status):
        audio_queue.put(indata.copy())

    def worker():
        print("录音同传系统已启动...")
        buffer = []
        trans_history = [] # 存储最近几句识别结果作为上下文
        samples_per_chunk = int(samplerate * args.chunk)
        from scipy.signal import resample

        with sd.InputStream(device=args.device_id, channels=channels, samplerate=samplerate, callback=callback):
            while True:
                data = audio_queue.get()
                buffer.append(data)
                if sum(len(b) for b in buffer) >= samples_per_chunk:
                    chunk = np.concatenate(buffer)
                    buffer = []
                    if channels > 1: chunk = np.mean(chunk, axis=1)
                    else: chunk = chunk.flatten()
                    
                    if np.abs(chunk).max() < 0.005: continue

                    if samplerate != 16000:
                        num_samples = int(len(chunk) * 16000 / samplerate)
                        chunk = resample(chunk, num_samples)
                    
                    temp_wav = f"trans_chunk_{int(time.time())}.wav"
                    sf.write(temp_wav, chunk, 16000)
                    
                    try:
                        # ASR 识别
                        results = asr_model.transcribe(audio=[temp_wav], context="", language=gui.lang_list[gui.lang_idx])
                        if results:
                            res = results[0] if isinstance(results, list) else results
                            raw_text = "".join(str(s.text) for s in (res if hasattr(res, '__iter__') else [res])).strip()
                            if raw_text and raw_text != "nan":
                                print(f"原: {raw_text}")
                                gui.update_raw(raw_text)
                                
                                # 只有在双语或仅译文模式下才翻译
                                if gui.display_mode != 1:
                                    t_start = time.time()
                                    # 构造上下文字符串（取最近 3 句）
                                    context_str = " ".join(trans_history[-3:]) if trans_history else ""
                                    cn_text = translator.translate(raw_text, history=context_str)
                                    
                                    print(f"译: {cn_text} (耗时: {time.time()-t_start:.2f}s)")
                                    gui.update_trans(cn_text)
                                    
                                    # 更新历史记录
                                    trans_history.append(raw_text)
                                    if len(trans_history) > 10: trans_history.pop(0)
                                else:
                                    gui.update_trans("") # 清空译文行
                                
                        if torch.cuda.is_available(): torch.cuda.empty_cache()
                    except Exception as e: print(f"Error: {e}")
                    finally:
                        if os.path.exists(temp_wav): os.remove(temp_wav)

    threading.Thread(target=worker, daemon=True).start()
    gui.run()

if __name__ == "__main__":
    main()
