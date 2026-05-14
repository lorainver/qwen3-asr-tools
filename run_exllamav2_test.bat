@echo off
setlocal
echo [1/3] 正在激活虚拟环境...
call D:\qwen3-asr\venv\Scripts\activate.bat

echo [2/3] 正在寻找 Visual Studio 编译环境...
set "VSWHERE=D:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" set "VSWHERE=C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"

for /f "usebackq tokens=*" %%i in (`^""%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath^"`) do (
  set "VS_PATH=%%i"
)

if not defined VS_PATH (
    echo [ERROR] 找不到 Visual Studio 编译环境，请确认是否安装了 C++ 编译工具。
    exit /b 1
)

echo [OK] 找到 VS 路径: %VS_PATH%
call "%VS_PATH%\VC\Auxiliary\Build\vcvars64.bat"

echo [3/3] 启动 ExLlamaV2 测试...
python D:\qwen3-asr\test_exllamav2_gptq.py

pause
