@echo off
chcp 65001 >nul 2>&1
title qwen3-asr 服务管理
echo.
echo ========================================
echo   qwen3-asr 服务重启脚本
echo ========================================
echo.

echo [1/3] 停止旧进程...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Process python -EA SilentlyContinue | %%{ $c=(Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine; if($c -match 'qwen3-asr'){Stop-Process -Id $_.Id -Force; Write-Host \"  已停止 PID $($_.Id)\"} }"

timeout /t 2 /nobreak >nul

echo [2/3] 启动服务...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$env:NO_PROXY='localhost,127.0.0.1'; $env:PYTHONIOENCODING='utf-8'; Start-Process -FilePath 'D:\qwen3-asr\venv\Scripts\python.exe' -ArgumentList 'd:\qwen3-asr\web_app.py' -WorkingDirectory 'D:\qwen3-asr' -WindowStyle Hidden"

echo [3/3] 等待服务就绪...
:WAIT_LOOP
timeout /t 2 /nobreak >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try{$r=Invoke-WebRequest 'http://127.0.0.1:8000/api/kb/stats' -TimeoutSec 2 -EA Stop; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if %errorlevel% neq 0 goto WAIT_LOOP

echo.
echo ========================================
echo   ✅ 服务已启动！
echo   Web:  http://127.0.0.1:8000
echo   API:  http://127.0.0.1:8001
echo ========================================
echo.
start http://127.0.0.1:8000
pause
