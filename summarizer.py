import torch
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import gc
import json
from model_manager import model_manager
from config_loader import config

# 配置日志
logger = logging.getLogger(__name__)

class LongTextSummarizer:
    def __init__(self):
        # 从配置文件读取模型路径
        self.default_model_path = config['models']['llm']
        self.model_path = self.default_model_path
        self.current_model_id = 'qwen-general'  # 当前模型 ID
        
        # 可用模型列表
        self.available_models = config.get('models.llm_models', {})
        
        logger.info(f"Summarizer 默认模型: {self.model_path}")
        self.tokenizer = None
        self.model = None

    def get_available_models(self):
        """返回可用模型列表"""
        result = []
        for model_id, model_info in self.available_models.items():
            result.append({
                'id': model_id,
                'name': model_info.get('name', model_id),
                'description': model_info.get('description', ''),
                'current': model_id == self.current_model_id
            })
        return result

    def get_current_model(self):
        """返回当前模型信息"""
        if self.current_model_id in self.available_models:
            model_info = self.available_models[self.current_model_id]
            return {
                'id': self.current_model_id,
                'name': model_info.get('name', self.current_model_id),
                'path': model_info.get('path', self.model_path)
            }
        return {'id': self.current_model_id, 'name': 'Unknown', 'path': self.model_path}

    def switch_model(self, model_id):
        """切换模型（卸载当前模型，设置新模型路径）"""
        if model_id not in self.available_models:
            logger.warning(f"未知模型 ID: {model_id}")
            return False
        
        if model_id == self.current_model_id and self.model is not None:
            logger.info(f"模型 {model_id} 已加载，无需切换")
            return True
        
        # 卸载当前模型
        if self.model is not None:
            logger.info(f"卸载当前模型 {self.current_model_id}...")
            self._unload_model()
        
        # 设置新模型
        model_info = self.available_models[model_id]
        self.model_path = model_info.get('path', self.default_model_path)
        self.current_model_id = model_id
        logger.info(f"已切换到模型 {model_id}: {self.model_path}")
        return True

    def _load_model(self):
        if self.model is None:
            logger.info("Loading Summarizer Model...")
            model_manager.set_processing(True)
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
            # 注册实例（而非模型对象），这样 release_all 可以调用 _unload_model
            model_manager.register_summarizer(self)
            logger.info("Summarizer Model loaded.")

    def _unload_model(self):
        if self.model is not None:
            logger.info("Unloading Summarizer Model...")
            # 先删除模型和分词器
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            model_manager.unregister_summarizer()
            # 强制清理显存（多次 GC + synchronize + empty_cache）
            gc.collect()
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            gc.collect()
            model_manager.set_processing(False)
            # 打印清理后的内存状态
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"Summarizer Model unloaded. Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB")
        else:
            model_manager.set_processing(False)

    def summarize(self, text, chunk_size=1500, yield_progress=None):
        """
        长文本总结：先分段局部总结，再全局融合。
        如果 yield_progress 存在，应当是一个可以通过 yield 传递进度的生成器回调。
        """
        self._load_model()
        final_result = None
        try:
            # 1. 文本切片
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            local_summaries = []
            
            total_steps = len(chunks) + 1 # 局部总结 N 步 + 最终全局总结 1 步
            current_step = 0

            # 2. 局部总结
            for i, chunk in enumerate(chunks):
                # 检查取消信号
                if model_manager.is_cancelled():
                    if yield_progress:
                        yield json.dumps({"status": "cancelled", "message": "任务已被用户取消"})
                    return
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
            final_prompt = f'以下是长篇会议记录的各个分段总结。请你将它们整合成一份有条理、带 Point（项目符号）的"一页纸精华"（需要包含：会议主题猜测、核心要点梳理、结论或行动项）：\n\n{combined_summaries}'
            
            messages = [{"role": "user", "content": final_prompt}]
            input_ids = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                output_ids = self.model.generate(input_ids, max_new_tokens=1024, do_sample=False)
                
            final_result = self.tokenizer.decode(output_ids[0][len(input_ids[0]):], skip_special_tokens=True)

        except torch.cuda.OutOfMemoryError:
            logger.error("GPU 显存不足！请关闭其他程序后重试。")
            if yield_progress:
                yield json.dumps({"status": "error", "message": "GPU 显存不足，请释放显存后重试"})
        except Exception as e:
            logger.error(f"总结过程出错: {e}")
            import traceback
            traceback.print_exc()
            if yield_progress:
                yield json.dumps({"status": "error", "message": f"总结出错: {e}"})
        finally:
            # 🔑 无论如何都卸载模型，防止显存泄漏
            self._unload_model()

        # 返回最终结果
        if yield_progress and final_result:
            yield json.dumps({"status": "done", "result": final_result})
        elif not yield_progress:
            return final_result

    def chat(self, messages):
        """
        通用对话接口
        messages 格式为: [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        """
        # 如果被取消，直接返回提示
        if model_manager.is_cancelled():
            return "（任务已被取消）"
            
        self._load_model()
        try:
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
            logger.debug(f"Chat response: {response[:100]}...")
            return response.strip()
        except torch.cuda.OutOfMemoryError:
            logger.error("GPU 显存不足！请关闭其他程序后重试。")
            raise
        except Exception as e:
            logger.error(f"对话出错: {e}")
            raise
        finally:
            # 对话频率高暂不卸载（显存充裕），若需释放去掉下面注释
            # self._unload_model()
            model_manager.set_processing(False)
