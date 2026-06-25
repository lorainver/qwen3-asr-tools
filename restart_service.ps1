# ============================================
#  qwen3-asr 服务重启脚本
#  用法: 右键 → 使用 PowerShell 运行
#        或在终端执行: .\restart_service.ps1
# ============================================

$ErrorActionPreference = "SilentlyContinue"
$venvPython = "D:\qwen3-asr\venv\Scripts\python.exe"
$workDir = "D:\qwen3-asr"
$env:NO_PROXY = "localhost,127.0.0.1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  qwen3-asr 服务管理脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 停止旧进程 ──
Write-Host "[1/3] 停止旧进程..." -ForegroundColor Yellow

$killed = 0
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmd -match 'qwen3-asr') {
        Stop-Process -Id $_.Id -Force
        $killed++
        Write-Host "  已停止 PID $($_.Id)" -ForegroundColor DarkGray
    }
}

# 等待端口释放
$waitCount = 0
while ($waitCount -lt 10) {
    $busy = Get-NetTCPConnection -LocalPort 8000,8001 -ErrorAction SilentlyContinue
    if (-not $busy) { break }
    Start-Sleep -Milliseconds 500
    $waitCount++
}

if ($killed -gt 0) {
    Write-Host "  共停止 $killed 个进程" -ForegroundColor Green
} else {
    Write-Host "  无运行中的进程" -ForegroundColor DarkGray
}

# ── 2. 检查端口 ──
Write-Host "[2/3] 检查端口..." -ForegroundColor Yellow

$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port8001 = Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue

if ($port8000 -or $port8001) {
    Write-Host "  ⚠️ 端口仍被占用，请手动检查" -ForegroundColor Red
    if ($port8000) { Write-Host "    端口 8000: PID $($port8000.OwningProcess)" -ForegroundColor Red }
    if ($port8001) { Write-Host "    端口 8001: PID $($port8001.OwningProcess)" -ForegroundColor Red }
    Read-Host "按 Enter 退出"
    exit 1
}
Write-Host "  端口 8000/8001 空闲 ✓" -ForegroundColor Green

# ── 3. 启动服务 ──
Write-Host "[3/3] 启动服务..." -ForegroundColor Yellow

# 后台启动 web_app.py（会自动拉起 ai_worker）
Start-Process -FilePath $venvPython -ArgumentList "d:\qwen3-asr\web_app.py" `
    -WorkingDirectory $workDir `
    -WindowStyle Hidden

# 等待服务就绪
Write-Host "  等待服务就绪..." -ForegroundColor DarkGray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/kb/stats" -TimeoutSec 2 -ErrorAction Stop
        if ($res.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($ready) {
    Write-Host "  ✅ 服务启动成功!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Web 服务:  http://127.0.0.1:8000" -ForegroundColor White
    Write-Host "  AI Worker: http://127.0.0.1:8001" -ForegroundColor White
    Write-Host "  知识库:    http://127.0.0.1:8000 (📊 群聊分析)" -ForegroundColor White
} else {
    Write-Host "  ⚠️ 服务可能还在启动中" -ForegroundColor Yellow
    Write-Host "  请稍后访问 http://127.0.0.1:8000" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 自动打开浏览器
Start-Process "http://127.0.0.1:8000"

Read-Host "按 Enter 关闭此窗口"
