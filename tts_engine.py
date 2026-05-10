import asyncio
import edge_tts
import os
import hashlib
import numpy as np

class EdgeEngine:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    async def stream_speech(self, text):
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            print(f"EdgeTTS Error: {e}")

class SherpaEngine:
    def __init__(self):
        self.tts = None
        # 使用绝对路径定位模型组件
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        model_root = os.path.join(self.base_dir, "models", "tts", "vits-icefall-zh-aishell3")
        
        self.model_path = os.path.join(model_root, "model.onnx")
        self.tokens_path = os.path.join(model_root, "tokens.txt")
        self.lexicon_path = os.path.join(model_root, "lexicon.txt")
        # 规则文件
        self.date_fst = os.path.join(model_root, "date.fst")
        self.number_fst = os.path.join(model_root, "number.fst")
        self.phone_fst = os.path.join(model_root, "phone.fst")
        
        self._initialized = False

    def _lazy_init(self):
        if self._initialized:
            return
        
        if not os.path.exists(self.model_path):
            print(f"Error: 离线模型文件不存在 at {self.model_path}")
            return

        import sherpa_onnx
        vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
            model=self.model_path,
            tokens=self.tokens_path,
            lexicon=self.lexicon_path,
            data_dir="",
            noise_scale=0.667,
            noise_scale_w=0.8,
            length_scale=1.0,
        )
        
        model_config = sherpa_onnx.OfflineTtsModelConfig(
            vits=vits_config,
            num_threads=2,
            debug=False,
            provider="cpu",
        )
        
        config = sherpa_onnx.OfflineTtsConfig(
            model=model_config,
            rule_fsts=f"{self.date_fst},{self.number_fst},{self.phone_fst}",
            max_num_sentences=1,
        )
        
        self.tts = sherpa_onnx.OfflineTts(config)
        self._initialized = True
        print("Sherpa-ONNX 离线语音引擎初始化完成。")

    async def stream_speech(self, text):
        self._lazy_init()
        if not self.tts:
            return

        # 文本预清洗
        import re
        # 1. 去掉 Markdown 标记
        clean_text = re.sub(r'[*#>`\-]', '', text)
        # 2. 全角标点转换，所有引号类直接删掉（模型不认识）
        replacements = {
            '（': '(', '）': ')', '，': ',', '。': '.',
            '：': ':', '；': ';', '？': '?', '！': '!',
            '\u201c': '', '\u201d': '', '\u2018': '', '\u2019': '',
            '"': '', "'": '',
            '－': '-', '—': '-'
        }
        for old, new in replacements.items():
            clean_text = clean_text.replace(old, new)
        
        # 3. 只保留中文、英文、数字和基础标点
        clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.:;?!()\-\/]', '', clean_text)
        
        # 4. 合并空格
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if not clean_text:
            return

        try:
            loop = asyncio.get_event_loop()
            audio = await loop.run_in_executor(None, self.tts.generate, clean_text)
            
            if audio is None or not hasattr(audio, 'samples'):
                print("SherpaTTS Error: 推理返回结果无效")
                return

            import io
            import wave
            
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.tts.sample_rate)
                    samples_np = np.array(audio.samples, dtype=np.float32)
                    # 音量增益，放大 5 倍后限幅防破音
                    VOLUME_GAIN = 5.0
                    samples_np = np.clip(samples_np * VOLUME_GAIN, -1.0, 1.0)
                    samples = (samples_np * 32767).astype(np.int16)
                    wav_file.writeframes(samples.tobytes())
                
                wav_data = wav_io.getvalue()
                
            chunk_size = 4096
            for i in range(0, len(wav_data), chunk_size):
                yield wav_data[i:i+chunk_size]
                
        except Exception as e:
            import traceback
            print("SherpaTTS Exception details:")
            traceback.print_exc()

class TTSEngine:
    def __init__(self):
        self.edge = EdgeEngine()
        self.sherpa = SherpaEngine()
        self.mode = "edge"  # 默认在线模式

    def set_mode(self, mode):
        if mode in ["edge", "sherpa"]:
            self.mode = mode
            print(f"TTS 模式切换至: {mode}")

    async def stream_speech(self, text):
        if self.mode == "sherpa":
            async for chunk in self.sherpa.stream_speech(text):
                yield chunk
        else:
            async for chunk in self.edge.stream_speech(text):
                yield chunk

    async def generate_speech(self, text, output_path):
        """全量保存功能，用于缓存"""
        try:
            with open(output_path, "wb") as f:
                async for chunk in self.stream_speech(text):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"Save TTS Error: {e}")
            return False
