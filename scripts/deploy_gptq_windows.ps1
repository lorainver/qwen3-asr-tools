# GPTQ 模型部署脚本（Windows + Python 3.14）
# 使用方法：以管理员身份运行

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "GPTQ 模型部署脚本" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 CUDA
Write-Host "[1/6] 检查 CUDA 安装..." -ForegroundColor Yellow
if (Test-Path "D:\NVIDIA\CUDA\v12.1\bin\nvcc.exe") {
    Write-Host "   CUDA 12.1 已安装" -ForegroundColor Green
} else {
    Write-Host "   请先安装 CUDA 12.1" -ForegroundColor Red
    Write-Host "   下载链接：https://developer.nvidia.com/cuda-12-1-0-download-archive"
    exit 1
}

# 2. 检查 VS Build Tools
Write-Host "[2/6] 检查 VS Build Tools..." -ForegroundColor Yellow
$vsPath = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
if (Test-Path $vsPath) {
    Write-Host "   VS Build Tools 已安装" -ForegroundColor Green
} else {
    Write-Host "   请先安装 VS Build Tools 2022" -ForegroundColor Red
    Write-Host "   下载链接：https://visualstudio.microsoft.com/downloads/"
    exit 1
}

# 3. 设置环境变量
Write-Host "[3/6] 设置环境变量..." -ForegroundColor Yellow
$env:CUDA_HOME = "D:\NVIDIA\CUDA\v12.1"
$env:CUDA_PATH = "D:\NVIDIA\CUDA\v12.1"
$env:TORCH_COMPILE_DISABLE = "1"
$env:Path = "D:\NVIDIA\CUDA\v12.1\bin;" + $env:Path
Write-Host "   环境变量已设置" -ForegroundColor Green

# 4. 安装 Python 依赖
Write-Host "[4/6] 安装 Python 依赖..." -ForegroundColor Yellow
& D:\qwen3-asr\venv\Scripts\pip.exe install gptqmodel==2.2.0 optimum transformers accelerate safetensors --quiet
& D:\qwen3-asr\venv\Scripts\pip.exe uninstall auto-gptq -y 2>$null
Write-Host "   Python 依赖已安装" -ForegroundColor Green

# 5. 下载模型（如果不存在）
Write-Host "[5/6] 检查模型文件..." -ForegroundColor Yellow
$modelPath = "D:\qwen3-asr\models\Qwen\Qwen2.5-7B-Instruct-GPTQ-Int4"
if (-not (Test-Path $modelPath)) {
    Write-Host "   正在下载模型..." -ForegroundColor Yellow
    & D:\qwen3-asr\venv\Scripts\python.exe -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4',
    local_dir=r'$modelPath'
)
"
    Write-Host "   模型下载完成" -ForegroundColor Green
} else {
    Write-Host "   模型已存在" -ForegroundColor Green
}

# 6. 提示修改 optimum
Write-Host "[6/6] 部署完成！" -ForegroundColor Yellow
Write-Host ""
Write-Host "请手动修改 optimum/gptq/quantizer.py:" -ForegroundColor Cyan
Write-Host "文件位置: D:\qwen3-asr\venv\Lib\site-packages\optimum\gptq\quantizer.py" -ForegroundColor White
Write-Host ""
Write-Host "修改内容:" -ForegroundColor Cyan
Write-Host "1. 导入部分: hf_select_quant_linear 替代 hf_select_quant_linear_v2" -ForegroundColor White
Write-Host "2. select_quant_linear 方法: checkpoint_format 替代 format" -ForegroundColor White
Write-Host "3. 移除 quant_method 参数" -ForegroundColor White
Write-Host ""
Write-Host "详细修改内容请参考文档: docs/GPTQ_Deployment_Guide_Windows.md" -ForegroundColor Yellow
