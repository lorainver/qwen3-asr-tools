import os
import torch
import logging
import gc
import json
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TextIteratorStreamer, AutoConfig
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from threading import Thread
import requests
from model_manager import model_manager
from config_loader import config

# 配置日志
logger = logging.getLogger(__name__)

class LongTextSummarizer:
    def __init__(self):
        # 从配置文件读取模型路径
        self.default_model_path = config['models']['llm']
        self.model_path = self.default_model_path
        self.current_model_id = 'qwen-ollama-7b'
        self.available_models = config['models'].get('llm_models', {})
        self.tokenizer = None
        self.processor = None
        self.model = None
        self.api_url = None
        self.is_remote = False
        
        # 启动时立即同步模型状态（确保远程标志被正确设置）
        self.switch_model(self.current_model_id)

    def get_available_models(self):
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
        if self.current_model_id in self.available_models:
            model_info = self.available_models[self.current_model_id]
            return {'id': self.current_model_id, 'name': model_info.get('name', self.current_model_id), 'path': model_info.get('path', self.model_path)}
        return {'id': self.current_model_id, 'name': 'Unknown', 'path': self.model_path}

    def switch_model(self, model_id):
        if model_id not in self.available_models:
            logger.warning(f"⚠️ 切换失败: 未知的模型 ID '{model_id}'")
            return False
        if model_id == self.current_model_id and self.model is not None:
            logger.info(f"✓ 模型 '{model_id}' 已加载，无需切换")
            return True
        if self.model is not None:
            logger.info(f"⏳ 卸载当前模型 '{self.current_model_id}'...")
            self._unload_model()
        model_info = self.available_models[model_id]
        self.model_path = model_info.get('path', self.default_model_path)
        self.current_model_id = model_id
        
        # 处理远程模型标识
        self.api_url = model_info.get('api_url')
        self.is_remote = model_info.get('is_remote', False)
        
        if self.is_remote:
            logger.info(f"🌐 已切换到远程模型 '{model_id}' -> {self.api_url}")
        else:
            logger.info(f"✅ 已切换到本地模型 '{model_id}' -> {self.model_path}")
        return True

    def _load_model(self):
        if self.model is None:
            logger.info(f"Loading Summarizer Model: {self.current_model_id}...")
            model_manager.set_processing(True)
            
            # 禁用 Triton JIT 编译（Windows 不支持 Triton）
            # 这对于 GPTQ 等预量化模型是必要的
            os.environ['TORCH_COMPILE_DISABLE'] = '1'
            try:
                import torch._dynamo
                torch._dynamo.config.disable = True
            except Exception:
                pass
            
            if self.current_model_id == 'qwen-vl':
                self.processor = AutoProcessor.from_pretrained(self.model_path)
                bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
                self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    self.model_path, 
                    quantization_config=bnb_config, 
                    device_map="auto", 
                    torch_dtype=torch.float16,
                    attn_implementation="sdpa"
                )
                self.tokenizer = self.processor.tokenizer
            else:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                
                # 检查模型是否已经有量化配置（如 GPTQ/AWQ）
                model_config = AutoConfig.from_pretrained(self.model_path)
                
                if hasattr(model_config, 'quantization_config') and model_config.quantization_config:
                    # 模型已量化，直接加载（不传递 quantization_config）
                    logger.info(f"✓ 模型已量化，跳过 BitsAndBytesConfig: {self.model_path}")
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_path, 
                        device_map="auto",
                        attn_implementation="sdpa"
                    )
                else:
                    # 模型未量化，使用 BitsAndBytesConfig 进行 4bit 量化
                    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_path, 
                        quantization_config=bnb_config, 
                        device_map="auto",
                        attn_implementation="sdpa"
                    )
            
            model_manager.register_summarizer(self)

    def _unload_model(self):
        if self.model is not None:
            logger.info("Unloading Summarizer Model...")
            del self.model
            if self.tokenizer: del self.tokenizer
            if self.processor: del self.processor
            self.model = self.tokenizer = self.processor = None
            model_manager.unregister_summarizer()
            gc.collect()
            torch.cuda.empty_cache()
            model_manager.set_processing(False)

    def chat(self, messages):
        if self.is_remote:
            return self._chat_remote(messages)
            
        self._load_model()
        try:
            if self.current_model_id == 'qwen-vl':
                text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.model.device)
            else:
                prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = self.tokenizer([prompt], return_tensors="pt").to(self.model.device)
            
            with torch.no_grad():
                output_ids = self.model.generate(**inputs, max_new_tokens=2048, do_sample=True, temperature=0.7)
            
            if self.current_model_id == 'qwen-vl':
                generated_ids = [oid[len(iids):] for iids, oid in zip(inputs.input_ids, output_ids)]
                return self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            return self.tokenizer.decode(output_ids[0][len(inputs.input_ids[0]):], skip_special_tokens=True).strip()
        finally:
            model_manager.set_processing(False)

    def _chat_remote(self, messages):
        logger.info(f"🚀 正在向远程服务器请求: {self.api_url}")
        model_info = self.available_models.get(self.current_model_id, {})
        remote_model = model_info.get('remote_model_name', self.current_model_id)
        
        # 针对本地 Ollama 的特殊处理：如果 ID 叫 qwen-ollama-7b，但实际模型叫 qwen2.5:7b
        if self.current_model_id == 'qwen-ollama-7b':
            remote_model = 'qwen2.5:7b'

        try:
            payload = {
                "model": remote_model,
                "messages": messages,
                "stream": False,
                "temperature": 0.7
            }
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            error_msg = f"❌ 远程请求失败: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def chat_stream(self, messages):
        if self.is_remote:
            yield from self._chat_stream_remote(messages)
            return

        self._load_model()
        try:
            if self.current_model_id == 'qwen-vl':
                text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.model.device)
            else:
                prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = self.tokenizer([prompt], return_tensors="pt").to(self.model.device)

            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(**inputs, max_new_tokens=2048, do_sample=True, temperature=0.7, streamer=streamer)
            thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
            thread.start()
            
            for new_text in streamer:
                if new_text:
                    yield new_text
            thread.join()
        finally:
            model_manager.set_processing(False)

    def _chat_stream_remote(self, messages):
        logger.info(f"🚀 正在向远程服务器发起流式请求: {self.api_url}")
        model_info = self.available_models.get(self.current_model_id, {})
        remote_model = model_info.get('remote_model_name', self.current_model_id)
        
        # 针对本地 Ollama 的特殊处理
        if self.current_model_id == 'qwen-ollama-7b':
            remote_model = 'qwen2.5:7b'

        try:
            payload = {
                "model": remote_model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7
            }
            response = requests.post(self.api_url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if not line: continue
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_content = line_str[6:].strip()
                    if data_content == "[DONE]": break
                    
                    try:
                        chunk = json.loads(data_content)
                        token = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if token:
                            yield token
                    except Exception:
                        continue
        except Exception as e:
            yield f"❌ 远程流式请求失败: {str(e)}"
