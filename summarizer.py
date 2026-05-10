import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import gc
import json

class LongTextSummarizer:
    def __init__(self, model_path=r"D:\qwen3-asr\models\Qwen\Qwen2.5-1.5B-Instruct"):
        self.model_path = model_path
        self.tokenizer = None
        self.model = None

    def _load_model(self):
        if self.model is None:
            print("Loading Summarizer Model...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4"
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                quantization_config=bnb_config,
                device_map="auto"
            )
            print("Summarizer Model loaded.")

    def _unload_model(self):
        if self.model is not None:
            print("Unloading Summarizer Model...")
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            gc.collect()
            torch.cuda.empty_cache()
            print("Summarizer Model unloaded.")

    def summarize(self, text, chunk_size=1500, yield_progress=None):
        """
        长文本总结：先分段局部总结，再全局融合。
        如果 yield_progress 存在，应当是一个可以通过 yield 传递进度的生成器回调。
        """
        self._load_model()
        
        # 1. 文本切片
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        local_summaries = []
        
        total_steps = len(chunks) + 1 # 局部总结 N 步 + 最终全局总结 1 步
        current_step = 0

        # 2. 局部总结
        for i, chunk in enumerate(chunks):
            prompt = f"请简要总结以下会议记录片段的核心内容，提取关键信息（字数控制在200字内）：\n{chunk}"
            messages = [{"role": "user", "content": prompt}]
            input_ids = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                output_ids = self.model.generate(input_ids, max_new_tokens=256, do_sample=False)
            
            summary = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)
            local_summaries.append(summary)
            
            current_step += 1
            if yield_progress:
                yield json.dumps({"status": "processing", "step": current_step, "total": total_steps, "message": f"正在处理第 {i+1}/{len(chunks)} 段文本..."})

        # 3. 全局总融合
        if yield_progress:
            yield json.dumps({"status": "processing", "step": total_steps, "total": total_steps, "message": "正在生成最终的全局精华摘要..."})
            
        combined_summaries = "\n\n".join([f"片段{i+1}: {s}" for i, s in enumerate(local_summaries)])
        final_prompt = f"以下是长篇会议记录的各个分段总结。请你将它们整合成一份有条理、带 Point（项目符号）的“一页纸精华”（需要包含：会议主题猜测、核心要点梳理、结论或行动项）：\n\n{combined_summaries}"
        
        messages = [{"role": "user", "content": final_prompt}]
        input_ids = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
        
        with torch.no_grad():
            output_ids = self.model.generate(input_ids, max_new_tokens=1024, do_sample=False)
            
        final_summary = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)
        
        # 完成后卸载模型释放显存
        self._unload_model()
        
        if yield_progress:
            yield json.dumps({"status": "done", "result": final_summary})
        else:
            return final_summary

    def chat(self, messages):
        """
        通用对话接口
        messages 格式为: [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        """
        self._load_model()
        
        input_ids = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=True, 
            add_generation_prompt=True, 
            return_tensors="pt"
        ).to("cuda")
        
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids, 
                max_new_tokens=512, 
                do_sample=True, 
                temperature=0.7,
                top_p=0.9
            )
            
        response = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)
        
        # 对话通常频率高，如果你显存够（8GB），可以考虑注释掉下面这行不频繁卸载
        # self._unload_model() 
        
        return response.strip()
