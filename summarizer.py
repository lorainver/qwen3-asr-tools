import os
import logging
import gc
import json
import requests
import threading
from model_manager import model_manager
from config_loader import config

# 配置日志
logger = logging.getLogger(__name__)

class LongTextSummarizer:
    def __init__(self):
        # 从配置文件读取模型路径
        self.default_model_path = config['models']['llm']
        self.model_path = self.default_model_path
        self.current_model_id = 'qwen-ollama-3b'
        self.available_models = config['models'].get('llm_models', {})
        self.tokenizer = None
        self.processor = None
        self.model = None
        self.api_url = None
        self.is_remote = False
        self._lock = threading.Lock()
        
        # 启动时立即同步模型状态（确保远程标志被正确设置）
        self.switch_model(self.current_model_id)

    def get_available_models(self):
        result = []
        # 1. 添加配置文件中的本地原生模型
        for model_id, model_info in self.available_models.items():
            if not model_info.get('is_remote', False):
                result.append({
                    'id': model_id,
                    'name': model_info.get('name', model_id),
                    'category': 'local',
                    'description': model_info.get('description', ''),
                    'current': model_id == self.current_model_id
                })
        
        # 2. 获取 Ollama 模型
        ollama_models = self._get_ollama_models_dynamic()
        for m in ollama_models:
            m_id = f"ollama:{m['name']}"
            result.append({
                'id': m_id,
                'name': f"Ollama: {m['name']}",
                'category': 'ollama',
                'description': f"Ollama 驱动的 {m['name']} 模型",
                'current': m_id == self.current_model_id or self.current_model_id in self.available_models and self.available_models[self.current_model_id].get('model_id') == m['name']
            })

        # 3. 添加远程模型
        for model_id, model_info in self.available_models.items():
            if model_info.get('is_remote', False) and 'ollama' not in model_id:
                result.append({
                    'id': model_id,
                    'name': model_info.get('name', model_id),
                    'category': 'remote',
                    'description': model_info.get('description', ''),
                    'current': model_id == self.current_model_id
                })
        
        return result

    def _get_ollama_models_dynamic(self):
        """动态从本地 Ollama 获取模型列表"""
        try:
            # 尝试 127.0.0.1 避开 localhost 解析延迟或 503
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2, proxies={'http': None, 'https': None})
            if resp.status_code == 200:
                return resp.json().get('models', [])
        except Exception as e:
            logger.warning(f"无法获取 Ollama 模型列表: {e}")
        return []

    def get_current_model(self):
        if self.current_model_id in self.available_models:
            model_info = self.available_models[self.current_model_id]
            return {'id': self.current_model_id, 'name': model_info.get('name', self.current_model_id), 'path': model_info.get('path', self.model_path)}
        return {'id': self.current_model_id, 'name': 'Unknown', 'path': self.model_path}

    def _is_ollama_model(self, model_id):
        if not model_id:
            return False
        if model_id.startswith("ollama:"):
            return True
        model_info = self.available_models.get(model_id)
        if model_info and model_info.get('is_remote', False):
            api_url = model_info.get('api_url', '')
            if api_url and "11434" in api_url:
                return True
        return False

    def _get_ollama_model_name(self, model_id):
        if not model_id:
            return None
        if model_id.startswith("ollama:"):
            return model_id.split(":", 1)[1]
        model_info = self.available_models.get(model_id)
        if model_info:
            return model_info.get('model_id', model_id)
        return None

    def _unload_ollama_model(self, model_name: str):
        """向本地 Ollama 服务发送请求，立即从显存中释放指定模型"""
        try:
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": model_name,
                "keep_alive": 0
            }
            logger.info(f"正在通知 Ollama 卸载模型以释放 GPU 显存: {model_name}...")
            resp = requests.post(url, json=payload, timeout=3.0)
            if resp.status_code == 200:
                logger.info(f"✓ Ollama 模型 '{model_name}' 已成功从 GPU 显存中退掉！")
            else:
                logger.warning(f"Ollama 返回异常状态码: {resp.status_code}")
        except Exception as e:
            logger.warning(f"无法向 Ollama 发送卸载请求 (可能本地 Ollama 未启动): {e}")

    def switch_model(self, model_id):
        # 【动作 A】：如果当前使用的是 Ollama 模型，且即将切换到本地模型，或者切换到不同的 Ollama 模型，则强行退掉旧 Ollama 显存
        if self._is_ollama_model(self.current_model_id):
            is_new_ollama = self._is_ollama_model(model_id)
            current_ollama_name = self._get_ollama_model_name(self.current_model_id)
            new_ollama_name = self._get_ollama_model_name(model_id)
            
            if not is_new_ollama or (is_new_ollama and current_ollama_name != new_ollama_name):
                # 切换到非 Ollama 模型，或者不同的 Ollama 模型，触发卸载
                if current_ollama_name:
                    self._unload_ollama_model(current_ollama_name)

        # 处理动态 Ollama 模型 ID (格式: ollama:name)
        if model_id.startswith("ollama:"):
            target_ollama_name = model_id.split(":", 1)[1]
            # 【动作 B】：如果要从本地切到 Ollama，自动帮用户把 1.5B 基础本地模型从显存中退掉
            if self.model is not None:
                logger.info("⚡ 检测到当前载入了本地模型，正在自动卸载以释放显存给 Ollama...")
                self._unload_model()
            
            self.current_model_id = model_id
            self.is_remote = True
            self.api_url = "http://127.0.0.1:11434/v1/chat/completions"
            # 我们动态构造一个 model_info 存储
            self.available_models[model_id] = {
                'name': f"Ollama: {target_ollama_name}",
                'model_id': target_ollama_name,
                'api_url': self.api_url,
                'is_remote': True
            }
            logger.info(f"✅ 已切换到动态 Ollama 模型 '{target_ollama_name}'")
            return True

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
        
        # 【动作 C】：如果要从本地切到 predefined Ollama 模型，也自动帮用户把本地模型退掉
        if self._is_ollama_model(model_id):
            if self.model is not None:
                logger.info("⚡ 检测到当前载入了本地模型，正在自动卸载以释放显存给 Ollama...")
                self._unload_model()

        if self.is_remote:
            logger.info(f"🌐 已切换到远程模型 '{model_id}' -> {self.api_url}")
        else:
            logger.info(f"✅ 已切换到本地模型 '{model_id}' -> {self.model_path}")
        return True

    def _load_model(self):
        if self.model is None:
            # 1.5 显存互斥锁：确保 ASR 模型已被释放以腾空 VRAM 给 LLM 模型
            model_manager.prepare_for_llm()
            
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, AutoConfig
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
            
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
        # 1. 如果当前是 Ollama 模型，且主动触发卸载（如一键释放），则通知 Ollama 释放显存
        if self._is_ollama_model(self.current_model_id):
            ollama_name = self._get_ollama_model_name(self.current_model_id)
            if ollama_name:
                self._unload_ollama_model(ollama_name)

        # 2. 如果是本地模型，执行标准的 HuggingFace 卸载与显存回收
        if self.model is not None:
            import torch
            logger.info("Unloading Summarizer Model...")
            del self.model
            if self.tokenizer: del self.tokenizer
            if self.processor: del self.processor
            self.model = self.tokenizer = self.processor = None
            model_manager.unregister_summarizer()
            gc.collect()
            torch.cuda.empty_cache()
            model_manager.set_processing(False)

    def chat(self, messages, max_new_tokens=None, enable_think=True):
        if max_new_tokens is None:
            max_new_tokens = config.get('chat', {}).get('max_new_tokens', 4096)
        if not max_new_tokens or max_new_tokens <= 0:
            max_new_tokens = None
        if self.is_remote:
            return self._chat_remote(messages, max_new_tokens, enable_think=enable_think)
            
        with self._lock:
            self._load_model()
            import torch
            from qwen_vl_utils import process_vision_info
            local_max_tokens = max_new_tokens or 8192
            try:
                if self.current_model_id == 'qwen-vl':
                    text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    image_inputs, video_inputs = process_vision_info(messages)
                    inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.model.device)
                else:
                    prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    inputs = self.tokenizer([prompt], return_tensors="pt").to(self.model.device)
                
                with torch.no_grad():
                    output_ids = self.model.generate(**inputs, max_new_tokens=local_max_tokens, do_sample=True, temperature=0.7)
                
                if self.current_model_id == 'qwen-vl':
                    generated_ids = [oid[len(iids):] for iids, oid in zip(inputs.input_ids, output_ids)]
                    return self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
                return self.tokenizer.decode(output_ids[0][len(inputs.input_ids[0]):], skip_special_tokens=True).strip()
            finally:
                model_manager.set_processing(False)

    def _chat_remote(self, messages, max_new_tokens=None, enable_think=True):
        is_ollama = self._is_ollama_model(self.current_model_id)
        api_url = self.api_url
        if is_ollama and api_url and "/v1/chat/completions" in api_url:
            api_url = api_url.replace("/v1/chat/completions", "/api/chat")

        logger.info(f"🚀 正在向远程服务器请求: {api_url} (Ollama原生模式: {is_ollama})")
        model_info = self.available_models.get(self.current_model_id, {})
        remote_model = model_info.get('model_id', self.current_model_id)

        # 动态解析鉴权 Headers
        headers = {}
        api_key = model_info.get('api_key')
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        custom_headers = model_info.get('headers')
        if custom_headers and isinstance(custom_headers, dict):
            headers.update(custom_headers)

        try:
            payload = {
                "model": remote_model,
                "messages": messages,
                "stream": False,
                "temperature": 0.7
            }
            if is_ollama:
                payload["think"] = enable_think
                if max_new_tokens is not None and max_new_tokens > 0:
                    payload["options"] = {"num_predict": max_new_tokens}
            else:
                payload["think"] = enable_think
                if max_new_tokens is not None and max_new_tokens > 0:
                    payload["max_tokens"] = max_new_tokens
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=60, proxies={'http': None, 'https': None})
            
            if response.status_code == 400:
                try:
                    err_msg = response.json().get('error', '')
                    if "does not support thinking" in err_msg:
                        payload.pop("think", None)
                        response = requests.post(api_url, json=payload, headers=headers, timeout=60, proxies={'http': None, 'https': None})
                except Exception:
                    pass
                    
            response.raise_for_status()
            data = response.json()
            
            if is_ollama:
                return data.get('message', {}).get('content', '')
            else:
                return data['choices'][0]['message']['content']
        except Exception as e:
            error_msg = f"❌ 远程请求失败: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def chat_stream(self, messages, enable_think=True, max_new_tokens=None):
        if max_new_tokens is None:
            max_new_tokens = config.get('chat', {}).get('max_new_tokens', 4096)
        if not max_new_tokens or max_new_tokens <= 0:
            max_new_tokens = None
        if self.is_remote:
            yield from self._chat_stream_remote(messages, enable_think=enable_think, max_new_tokens=max_new_tokens)
            return

        with self._lock:
            self._load_model()
            import torch
            from transformers import TextIteratorStreamer
            from threading import Thread
            local_max_tokens = max_new_tokens or 8192
            try:
                if self.current_model_id == 'qwen-vl':
                    text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    image_inputs, video_inputs = process_vision_info(messages)
                    inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to(self.model.device)
                else:
                    prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    inputs = self.tokenizer([prompt], return_tensors="pt").to(self.model.device)

                streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
                generation_kwargs = dict(**inputs, max_new_tokens=local_max_tokens, do_sample=True, temperature=0.7, streamer=streamer)
                thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
                thread.start()
                
                for new_text in streamer:
                    if new_text:
                        yield new_text
                thread.join()
            finally:
                model_manager.set_processing(False)

    def _chat_stream_remote(self, messages, enable_think=True, max_new_tokens=None):
        is_ollama = self._is_ollama_model(self.current_model_id)
        api_url = self.api_url
        if is_ollama and api_url and "/v1/chat/completions" in api_url:
            api_url = api_url.replace("/v1/chat/completions", "/api/chat")

        logger.info(f"🚀 正在向远程服务器发起流式请求: {api_url} (Ollama原生模式: {is_ollama}, Think: {enable_think})")
        model_info = self.available_models.get(self.current_model_id, {})
        remote_model = model_info.get('model_id', self.current_model_id)

        # 动态解析鉴权 Headers
        headers = {}
        api_key = model_info.get('api_key')
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        custom_headers = model_info.get('headers')
        if custom_headers and isinstance(custom_headers, dict):
            headers.update(custom_headers)

        # 构造发送给远程服务器的消息体
        local_messages = list(messages)

        try:
            payload = {
                "model": remote_model,
                "messages": local_messages,
                "stream": True,
                "temperature": 0.7
            }
            if is_ollama:
                payload["think"] = enable_think
                if max_new_tokens is not None and max_new_tokens > 0:
                    payload["options"] = {"num_predict": max_new_tokens}
            else:
                payload["think"] = enable_think
                if max_new_tokens is not None and max_new_tokens > 0:
                    payload["max_tokens"] = max_new_tokens
                    
            response = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=600, proxies={'http': None, 'https': None})
            
            if response.status_code == 400:
                try:
                    # requests stream=True might not read json immediately without closing, but we can check text
                    # Wait, if we read json, we can't reuse response. So let's use response.text or load it.
                    # Actually, if status code is 400, it's usually a small JSON error payload.
                    err_msg = response.json().get('error', '')
                    if "does not support thinking" in err_msg:
                        payload.pop("think", None)
                        response = requests.post(api_url, json=payload, headers=headers, stream=True, timeout=600, proxies={'http': None, 'https': None})
                except Exception:
                    pass
            
            response.raise_for_status()
            
            is_thinking = False
            
            if is_ollama:
                for line in response.iter_lines(chunk_size=1):
                    if not line: continue
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        reasoning = chunk.get('message', {}).get('thinking') or chunk.get('message', {}).get('reasoning') or ''
                        if reasoning:
                            if not is_thinking:
                                yield "<think>"
                                is_thinking = True
                            yield reasoning
                        
                        token = chunk.get('message', {}).get('content') or ''
                        if token:
                            if is_thinking:
                                yield "</think>"
                                is_thinking = False
                            yield token
                            
                        if chunk.get('done', False):
                            break
                    except Exception as ex:
                        logger.warning(f"解析 Ollama 原生流 chunk 失败: {ex}")
                        continue
            else:
                for line in response.iter_lines(chunk_size=1):
                    if not line: continue
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_content = line_str[6:].strip()
                        if data_content == "[DONE]": break
                        
                        try:
                            chunk = json.loads(data_content)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            
                            reasoning = delta.get('reasoning_content') or delta.get('reasoning') or delta.get('thought') or ''
                            if reasoning:
                                if not is_thinking:
                                    yield "<think>"
                                    is_thinking = True
                                yield reasoning
                            
                            token = delta.get('content', '')
                            if token:
                                if is_thinking:
                                    yield "</think>"
                                    is_thinking = False
                                yield token
                        except Exception:
                            continue
            
            if is_thinking:
                yield "</think>"
        except Exception as e:
            yield f"❌ 远程流式请求失败: {str(e)}"
