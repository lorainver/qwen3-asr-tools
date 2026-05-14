# -*- coding: utf-8 -*-
import sys
import os

def check_env():
    print("="*40)
    print("当前运行环境信息")
    print("="*40)
    print(f"Python 解释器: {sys.executable}")
    print(f"工作目录: {os.getcwd()}")
    
    try:
        import torch
        print(f"Torch 版本: {torch.__version__}")
        print(f"CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA 版本: {torch.version.cuda}")
            print(f"GPU 型号: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("未检测到 Torch")
        
    try:
        import exllamav2
        print(f"ExLlamaV2 版本: {exllamav2.__version__}")
    except ImportError:
        print("未检测到 ExLlamaV2")
    print("="*40)

if __name__ == "__main__":
    check_env()
