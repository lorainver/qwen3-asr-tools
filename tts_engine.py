import asyncio
import edge_tts
import os

class TTSEngine:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        """
        voice 默认使用微软最自然的晓晓声音。
        可选声音包括: zh-CN-YunxiNeural (男声), zh-CN-XiaoyiNeural 等。
        """
        self.voice = voice

    async def generate_speech(self, text, output_path):
        """将文本转换为音频文件 (全量保存)"""
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"TTS Error: {e}")
            return False

    async def stream_speech(self, text):
        """流式产生音频数据块"""
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            print(f"TTS Stream Error: {e}")

# 快速测试脚本 (仅在直接运行此文件时生效)
if __name__ == "__main__":
    engine = TTSEngine()
    asyncio.run(engine.generate_speech("你好，我是你的本地 AI 助理。", "test.mp3"))
    print("测试音频生成完毕: test.mp3")
