# -*- coding: utf-8 -*-
$vsPath = "D:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"
Write-Host "--- 正在定位 C++ 编译器 ---"
$clFile = Get-ChildItem -Path "$vsPath\VC\Tools\MSVC" -Filter "cl.exe" -Recurse | Where-Object { $_.FullName -like "*Hostx64\x64*" } | Select-Object -First 1

if ($null -eq $clFile) {
    Write-Error "找不到 cl.exe"
    exit
}

$clDir = $clFile.DirectoryName
Write-Host "找到编译器路径: $clDir"

# 设置环境变量
$env:Path = "$clDir;" + $env:Path
$env:CUDA_HOME = "D:\NVIDIA\CUDA\v12.1"

Write-Host "--- 启动满血推理测试 ---"
& "D:\qwen3-asr\venv_stable\Scripts\python.exe" "D:\qwen3-asr\test_stable_speed.py"
