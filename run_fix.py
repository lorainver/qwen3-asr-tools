# -*- coding: utf-8 -*-
import os
import subprocess
import sys

def run_with_vs_env():
    print("[1/3] 寻找 Visual Studio 编译环境...")
    
    # 常见的 vswhere 路径
    vswhere_path = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    if not os.path.exists(vswhere_path):
        vswhere_path = r"D:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
        
    if not os.path.exists(vswhere_path):
        print("[ERROR] 找不到 vswhere.exe，请确认安装了 Visual Studio Installer")
        return

    # 获取安装路径
    cmd = [vswhere_path, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"]
    try:
        vs_path = subprocess.check_output(cmd).decode('gbk').strip()
    except:
        print("[ERROR] 无法获取 VS 安装路径")
        return

    if not vs_path:
        print("[ERROR] 找不到满足条件的 VS 安装（需要 C++ 编译工具）")
        return

    print(f"[OK] 找到 VS 路径: {vs_path}")
    
    vcvars_bat = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvars64.bat")
    if not os.path.exists(vcvars_bat):
        print(f"[ERROR] 找不到 vcvars64.bat: {vcvars_bat}")
        return

    # 构建运行命令
    # 1. 激活 VS 环境
    # 2. 运行测试脚本
    test_script = r"D:\qwen3-asr\test_exllamav2_gptq.py"
    python_exe = sys.executable # 使用当前虚拟环境的 python
    
    final_cmd = f'"{vcvars_bat}" && "{python_exe}" "{test_script}"'
    
    print("[2/3] 正在启动编译并测试 (这可能需要几分钟，请耐心等待)...")
    
    # 使用 cmd /c 运行，因为它支持 && 和 call
    process = subprocess.Popen(f'cmd /c "{final_cmd}"', shell=True)
    process.wait()

if __name__ == "__main__":
    run_with_vs_env()
