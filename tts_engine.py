import asyncio
import edge_tts
import os
import hashlib
import numpy as np
import struct

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
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        model_root = os.path.join(self.base_dir, "models", "tts", "vits-icefall-zh-aishell3")
        
        self.model_path = os.path.join(model_root, "model.onnx")
        self.tokens_path = os.path.join(model_root, "tokens.txt")
        self.lexicon_path = os.path.join(model_root, "lexicon.txt")
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

    def _make_wav_header(self, sample_rate, num_channels=1, bits_per_sample=16):
        """生成流式 WAV 头（数据长度设为最大值，支持边生成边播放）"""
        header = b'RIFF'
        header += struct.pack('<I', 0xFFFFFFFF)  # 文件大小未知（流式）
        header += b'WAVE'
        header += b'fmt '
        header += struct.pack('<I', 16)
        header += struct.pack('<H', 1)            # PCM 格式
        header += struct.pack('<H', num_channels)
        header += struct.pack('<I', sample_rate)
        header += struct.pack('<I', sample_rate * num_channels * bits_per_sample // 8)
        header += struct.pack('<H', num_channels * bits_per_sample // 8)
        header += struct.pack('<H', bits_per_sample)
        header += b'data'
        header += struct.pack('<I', 0xFFFFFFFF)  # 数据大小未知（流式）
        return header

    async def stream_speech(self, text):
        self._lazy_init()
        if not self.tts:
            return

        # 文本预清洗
        import re
        clean_text = re.sub(r'[*#>`\-]', '', text)
        replacements = {
            '（': '(', '）': ')', '，': ',', '。': '.',
            '：': ':', '；': ';', '？': '?', '！': '!',
            '\u201c': '', '\u201d': '', '\u2018': '', '\u2019': '',
            '"': '', "'": '',
            '－': '-', '—': '-'
        }
        for old, new in replacements.items():
            clean_text = clean_text.replace(old, new)
        clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.:;?!()\-\/]', '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        if not clean_text:
            return

        # 分句处理：按句号、问号、感叹号切分，逐句合成逐句推送
        sentences = re.split(r'(?<=[.?!,])\s*', clean_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return

        try:
            loop = asyncio.get_event_loop()
            VOLUME_GAIN = 5.0

            # 先发送流式 WAV 头，浏览器立即准备好播放器
            yield self._make_wav_header(self.tts.sample_rate)

            for sentence in sentences:
                audio = await loop.run_in_executor(None, self.tts.generate, sentence)
                if audio is None or not hasattr(audio, 'samples'):
                    continue

                samples_np = np.array(audio.samples, dtype=np.float32)
                samples_np = np.clip(samples_np * VOLUME_GAIN, -1.0, 1.0)
                pcm_data = (samples_np * 32767).astype(np.int16).tobytes()

                # 逐块推送 PCM 数据
                chunk_size = 4096
                for i in range(0, len(pcm_data), chunk_size):
                    yield pcm_data[i:i+chunk_size]

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
