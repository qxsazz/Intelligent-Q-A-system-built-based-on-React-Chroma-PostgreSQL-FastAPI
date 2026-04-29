$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $projectRoot "frontend"

if (!(Test-Path $frontendDir)) {
  throw "frontend 目录不存在: $frontendDir"
}

Write-Host "正在启动前端终端..." -ForegroundColor Cyan

$frontendCmd = @"
cd '$frontendDir'
npm run dev
"@

Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd) | Out-Null

Write-Host "前端已发起启动。关闭请在前端窗口按 Ctrl + C。" -ForegroundColor Green
