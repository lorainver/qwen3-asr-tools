@echo off
chcp 65001 >nul 2>&1
title qwen3-asr 停止服务
echo.
echo 停止 qwen3-asr 服务...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$killed=0; Get-Process python -EA SilentlyContinue | %%{ $c=(Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine; if($c -match 'qwen3-asr'){Stop-Process -Id $_.Id -Force; $killed++; Write-Host \"  已停止 PID $($_.Id)\" } }; if($killed -eq 0){Write-Host '  无运行中的进程'} else {Write-Host \"  共停止 $killed 个进程\"}"

timeout /t 2 /nobreak >nul

REM 检查端口
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Get-NetTCPConnection -LocalPort 8000,8001 -EA SilentlyContinue; if($p){Write-Host '  ⚠️ 端口仍被占用'}else{Write-Host '  ✅ 端口已释放'}"

echo.
pause
