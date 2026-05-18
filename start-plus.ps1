$ErrorActionPreference = "Continue"
$startTime = (Get-Date)

# Start backend
$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"
Write-Output "=== [1/3] Starting Backend on 8001 ==="
$bProc = Start-Process -FilePath "python" -ArgumentList "-m app.main" -WorkingDirectory "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus" -PassThru -WindowStyle Normal
Write-Output "Backend PID: $($bProc.Id)"
Start-Sleep -Seconds 6

Write-Output "=== [2/3] Checking backend ==="
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 5
    Write-Output "Backend OK: $($r.Content)"
} catch {
    Write-Output "Backend check failed, but process may still be starting..."
}

Write-Output "=== [3/3] Starting Desktop with pnpm ==="
$env:MODE = "electron"
$dProc = Start-Process -FilePath "cmd" -ArgumentList "/c cd /d D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop && set MODE=electron&&pnpm dev:electron" -PassThru -WindowStyle Normal
Write-Output "Desktop PID: $($dProc.Id)"

Start-Sleep -Seconds 20

Write-Output "=== Checking ports ==="
Write-Output "Port 8001:"
netstat -ano | Select-String "8001.*LISTENING"
Write-Output "Port 1420:"
netstat -ano | Select-String "1420.*LISTENING"

Write-Output "=== Recent node processes ==="
$procs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" 2>$null
$procs | Where-Object { $_.CreationDate -gt $startTime } | ForEach-Object {
    Write-Output "  PID $($_.ProcessId) started $($_.CreationDate)"
    if ($_.CommandLine) {
        Write-Output "    $($_.CommandLine)"
    }
}