import os
import urllib.request
import tarfile

def setup_sherpa_model():
    # 使用绝对路径确保模型位置正确
    base_dir = r"D:\qwen3-asr\models\tts"
    os.makedirs(base_dir, exist_ok=True)
    
    filename = "vits-icefall-zh-aishell3.tar.bz2"
    url = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/{filename}"
    target_path = os.path.join(base_dir, filename)
    extract_dir = os.path.join(base_dir, "vits-icefall-zh-aishell3")
    
    if not os.path.exists(extract_dir):
        if not os.path.exists(target_path):
            print(f"开始下载离线模型至 D:\\qwen3-asr: {filename} ...")
            try:
                opener = urllib.request.build_opener()
                opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
                urllib.request.install_opener(opener)
                urllib.request.urlretrieve(url, target_path)
                print("下载完成。")
            except Exception as e:
                print(f"下载失败: {e}")
                return

        print("正在解压模型...")
        try:
            with tarfile.open(target_path, "r:bz2") as tar:
                tar.extractall(path=base_dir)
            print("解压完成！")
            os.remove(target_path)
        except Exception as e:
            print(f"解压失败: {e}")
    else:
        print("离线模型已存在。")

if __name__ == "__main__":
    setup_sherpa_model()
