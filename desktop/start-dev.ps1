$ErrorActionPreference = "Continue"
$env:MODE = "electron"
$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"
Write-Output "Starting Vite dev server..."
$proc = Start-Process -FilePath "cmd" -ArgumentList "/c cd /d D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop && set MODE=electron && npm run dev:electron" -PassThru -WindowStyle Normal
Write-Output "Started with PID: $($proc.Id)"
Start-Sleep -Seconds 15
Write-Output "Checking port 1420..."
netstat -ano | Select-String "1420"