# -*- coding: utf-8 -*-
import os
import sys

# 强制欺骗 Torch，让它以为显卡是 sm_90 (RTX 40系列)
# 这样它就会尝试运行已有的内核，而不是报错退出
os.environ["TORCH_CUDA_ARCH_LIST"] = "9.0"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# 强制注入路径
os.environ["CUDA_HOME"] = r"D:\NVIDIA\CUDA\v12.1"
os.environ["PATH"] = r"D:\NVIDIA\CUDA\v12.1\bin;D:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64;" + os.environ.get("PATH", "")

# 运行测试
print("正在尝试强制兼容模式 (欺骗架构为 sm_90)...")
import torch
print(f"检测到设备: {torch.cuda.get_device_name(0)}")

# 启动之前的测试脚本
import test_stable_speed
test_stable_speed.test_exllamav2_speed()
