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
        # 使用绝对路径定位模型
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(self.base_dir, "models", "tts", "vits-icefall-zh-aishell3", "model.onnx")
        self.tokens_path = os.path.join(self.base_dir, "models", "tts", "vits-icefall-zh-aishell3", "tokens.txt")
        self._initialized = False

    def _lazy_init(self):
        """延迟初始化，只有第一次使用离线引擎时才加载模型，节省内存"""
        if self._initialized:
            return
        
        if not os.path.exists(self.model_path):
            print(f"Error: 离线模型文件不存在 at {self.model_path}")
            return

        import sherpa_onnx
        # 配置离线模型参数
        vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
            model=self.model_path,
            tokens=self.tokens_path,
            lexicon="",
            data_dir="",
            noise_scale=0.667,
            noise_scale_w=0.8,
            length_scale=1.0,
        )
        
        model_config = sherpa_onnx.OfflineTtsModelConfig(
            vits=vits_config,
            num_threads=1,
            debug=False,
            provider="cpu", # 离线语音建议用 CPU，足够快且不占显存
        )
        
        config = sherpa_onnx.OfflineTtsConfig(
            model=model_config,
            rule_fsts="",
            max_num_sentences=1,
        )
        
        self.tts = sherpa_onnx.OfflineTts(config)
        self._initialized = True
        print("Sherpa-ONNX 离线语音引擎初始化完成。")

    async def stream_speech(self, text):
        """
        Sherpa-ONNX 的推理极快，但通常是一次性生成的。
        为了兼容流式接口，我们将生成后的 wav 数据分块返回。
        """
        self._lazy_init()
        if not self.tts:
            return

        try:
            # 在单独的线程中运行 CPU 密集型推理，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            audio = await loop.run_in_executor(None, self.tts.generate, text)
            
            # 将采样数据转换为 MP3/WAV 字节流 (这里简单处理为带头的 WAV)
            import io
            import wave
            
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.tts.sample_rate)
                    # 转换 float32 采样到 int16
                    samples = (audio.samples * 32767).astype(np.int16)
                    wav_file.writeframes(samples.tobytes())
                
                wav_data = wav_io.getvalue()
                
            # 分块 yield，模拟流式效果
            chunk_size = 4096
            for i in range(0, len(wav_data), chunk_size):
                yield wav_data[i:i+chunk_size]
                
        except Exception as e:
            print(f"SherpaTTS Error: {e}")

class TTSEngine:
    def __init__(self):
        self.edge = EdgeEngine()
        self.sherpa = SherpaEngine()
        self.mode = "edge" # 默认在线模式

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
        # 简单实现：通过流式接口收集并保存
        try:
            with open(output_path, "wb") as f:
                async for chunk in self.stream_speech(text):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"Save TTS Error: {e}")
            return False
