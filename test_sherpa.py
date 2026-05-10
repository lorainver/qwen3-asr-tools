import os
import numpy as np
import io
import wave
import sys

def test_sherpa():
    try:
        import sherpa_onnx
        print("Sherpa-ONNX 库加载成功。")
    except ImportError:
        print("错误: 未找到 sherpa-onnx 库。")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "models", "tts", "vits-icefall-zh-aishell3", "model.onnx")
    tokens_path = os.path.join(base_dir, "models", "tts", "vits-icefall-zh-aishell3", "tokens.txt")
    lexicon_path = os.path.join(base_dir, "models", "tts", "vits-icefall-zh-aishell3", "lexicon.txt")

    if not os.path.exists(model_path):
        print(f"错误: 模型文件未找到: {model_path}")
        return

    print("正在初始化引擎...")
    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
        model=model_path,
        tokens=tokens_path,
        lexicon=lexicon_path,
    )
    model_config = sherpa_onnx.OfflineTtsModelConfig(vits=vits_config)
    config = sherpa_onnx.OfflineTtsConfig(model=model_config)
    
    tts = sherpa_onnx.OfflineTts(config)
    print("引擎初始化成功。")

    test_text = "你好，这是离线语音测试。今天天气不错。"
    print(f"正在测试合成文本: {test_text}")
    
    audio = tts.generate(test_text)
    
    if audio and hasattr(audio, 'samples'):
        print(f"合成成功！音频长度: {len(audio.samples)} 采样点")
        output_file = "test_offline.wav"
        with wave.open(output_file, 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(tts.sample_rate)
            # 修复：先转 numpy 数组
            samples_np = np.array(audio.samples, dtype=np.float32)
            samples = (samples_np * 32767).astype(np.int16)
            f.writeframes(samples.tobytes())
        print(f"测试音频已保存至: {output_file}")
    else:
        print("错误: 合成失败，返回结果为空。")

if __name__ == "__main__":
    test_sherpa()
