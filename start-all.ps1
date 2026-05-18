$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"
$env:MODE = "electron"

$desktopDir = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop"
$backendDir = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"

Write-Output "=== Starting BiliTools-Plus Backend (port 8001) ==="
$backendProc = Start-Process -FilePath "python" -ArgumentList "-m app.main" -WorkingDirectory $backendDir -PassThru -WindowStyle Normal
Write-Output "Backend PID: $($backendProc.Id)"
Start-Sleep -Seconds 6

Write-Output "=== Checking backend health ==="
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 5
    Write-Output "Backend OK: $($r.Content)"
} catch {
    Write-Output "Backend FAILED: $($_.Exception.Message)"
}

Write-Output "=== Starting Desktop Dev Server ==="
$desktopProc = Start-Process -FilePath "cmd" -ArgumentList "/c cd /d $desktopDir && set MODE=electron&& npm run dev:electron" -PassThru -WindowStyle Normal
Write-Output "Desktop PID: $($desktopProc.Id)"

Start-Sleep -Seconds 15
Write-Output "=== Checking dev server ==="
netstat -ano | Select-String "1420"
Write-Output "=== All done ==="