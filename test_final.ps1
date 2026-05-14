# 自动化定位 Visual Studio 编译器并运行测试
$vsPath = "D:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"

echo "--- 正在定位 C++ 编译器 ---"
$clFile = Get-ChildItem -Path "$vsPath\VC\Tools\MSVC" -Filter "cl.exe" -Recurse | Where-Object { $_.FullName -like "*Hostx64\x64*" } | Select-Object -First 1

if ($null -eq $clFile) {
    Write-Error "错误：在 $vsPath 中找不到 cl.exe。请确认是否安装了 C++ 编译组件。"
    exit
}

$clDir = $clFile.DirectoryName
echo "找到编译器路径: $clDir"

# 设置环境变量
$env:Path = "$clDir;$env:Path"
$env:CUDA_HOME = "D:\NVIDIA\CUDA\v12.1"

echo "--- 正在启动满血测试 (venv_stable) ---"
& "D:\qwen3-asr\venv_stable\Scripts\python.exe" "D:\qwen3-asr\test_stable_speed.py"
