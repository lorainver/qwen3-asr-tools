import torch
import logging
import gc
import json
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TextIteratorStreamer
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from threading import Thread
from model_manager import model_manager
from config_loader import config

# 配置日志
logger = logging.getLogger(__name__)

class LongTextSummarizer:
    def __init__(self):
        # 从配置文件读取模型路径
        self.default_model_path = config['models']['llm']
        self.model_path = self.default_model_path
        self.current_model_id = 'qwen-general'
        self.available_models = config.get('models.llm_models', {})
        self.tokenizer = None
        self.processor = None
        self.model = None

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
            return False
        if model_id == self.current_model_id and self.model is not None:
            return True
        if self.model is not None:
            self._unload_model()
        model_info = self.available_models[model_id]
        self.model_path = model_info.get('path', self.default_model_path)
        self.current_model_id = model_id
        return True

    def _load_model(self):
        if self.model is None:
            logger.info(f"Loading Summarizer Model: {self.current_model_id}...")
            model_manager.set_processing(True)
            
            if self.current_model_id == 'qwen-vl':
                self.processor = AutoProcessor.from_pretrained(self.model_path)
                bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
                self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(self.model_path, quantization_config=bnb_config, device_map="auto", torch_dtype=torch.float16)
                self.tokenizer = self.processor.tokenizer
            else:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4")
                self.model = AutoModelForCausalLM.from_pretrained(self.model_path, quantization_config=bnb_config, device_map="auto")
            
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

    def chat_stream(self, messages):
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
