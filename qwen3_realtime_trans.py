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
        
        # 原文显示 (绿色)
        self.raw_label = tk.Label(
            self.frame, text="等待识别...", font=("Microsoft YaHei", 18, "bold"),
            fg="#00ff00", bg="#1a1a1a", wraplength=1050, justify="center"
        )
        self.raw_label.pack(expand=True, pady=(10, 0))
        
        # 翻译显示 (青色/白色)
        self.trans_label = tk.Label(
            self.frame, text="等待翻译...", font=("Microsoft YaHei", 20, "bold"),
            fg="#00ffff", bg="#1a1a1a", wraplength=1050, justify="center"
        )
        self.trans_label.pack(expand=True, pady=(0, 10))

        # 关闭按钮
        self.close_btn = tk.Label(self.frame, text=" × ", font=("Arial", 14), fg="#555", bg="#1a1a1a", cursor="hand2")
        self.close_btn.place(relx=1.0, rely=0.0, anchor="ne")
        self.close_btn.bind("<Button-1>", lambda e: self.root.destroy())

        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)
        
        # 模式状态: 0:双语, 1:仅原文, 2:仅译文
        self.display_mode = 0
        self.mode_names = ["双", "原", "译"]
        
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

    def cycle_mode(self, event):
        self.display_mode = (self.display_mode + 1) % 3
        self.mode_btn.config(text=self.mode_names[self.display_mode])
        # 切换布局显隐
        if self.display_mode == 1: # 仅原文
            self.trans_label.pack_forget()
            self.raw_label.pack(expand=True, fill=tk.BOTH)
        elif self.display_mode == 2: # 仅译文
            self.raw_label.pack_forget()
            self.trans_label.pack(expand=True, fill=tk.BOTH)
        else: # 双语
            self.raw_label.pack_forget()
            self.trans_label.pack_forget()
            self.raw_label.pack(expand=True, pady=(10, 0))
            self.trans_label.pack(expand=True, pady=(0, 10))
        print(f" >>> 显示模式: {self.mode_names[self.display_mode]}")

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
        self.raw_label.config(text=f"原: {text}")
    def update_trans(self, text):
        self.trans_label.config(text=f"译: {text}")

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

    def translate(self, text):
        if not text: return ""
        prompt = f"请将以下内容直接翻译成中文，不要输出任何解释：\n{text}"
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
                                    cn_text = translator.translate(raw_text)
                                    print(f"译: {cn_text} (耗时: {time.time()-t_start:.2f}s)")
                                    gui.update_trans(cn_text)
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
