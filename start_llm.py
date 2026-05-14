# -*- coding: utf-8 -*-
import os
import sys
import subprocess

# 1. 强制设定环境路径
# 请根据你的实际安装位置微调
CUDA_PATH = r"D:\NVIDIA\CUDA\v12.1"
VS_PATH = r"D:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"

os.environ["CUDA_HOME"] = CUDA_PATH
os.environ["PATH"] = os.path.join(CUDA_PATH, "bin") + os.path.pathsep + os.environ.get("PATH", "")

# 2. 找到 vcvars64.bat 用于编译支持
vcvars_bat = os.path.join(VS_PATH, r"VC\Auxiliary\Build\vcvars64.bat")

# 3. 构建运行命令
stable_python = r"D:\qwen3-asr\venv_stable\Scripts\python.exe"
test_script = r"D:\qwen3-asr\test_stable_speed.py"

if os.path.exists(vcvars_bat):
    # 如果有编译环境，先加载它
    final_cmd = f'"{vcvars_bat}" && "{stable_python}" "{test_script}"'
else:
    final_cmd = f'"{stable_python}" "{test_script}"'

print(f"正在启动满血版推理引擎...")
print(f"CUDA_HOME: {os.environ['CUDA_HOME']}")

# 4. 执行
subprocess.run(f'cmd /c "{final_cmd}"', shell=True)
