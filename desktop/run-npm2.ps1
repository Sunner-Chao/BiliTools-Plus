$env:MODE = "electron"
$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"

Write-Output "Starting npm via cmd..."
$cmdProc = Start-Process -FilePath "cmd" -ArgumentList "/c cd /d D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop && set MODE=electron&& call npm run dev:electron > D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-out.txt 2>&1" -PassThru -WindowStyle Normal
Write-Output "CMD PID: $($cmdProc.Id)"
Start-Sleep -Seconds 15

Write-Output "`n--- NPM output ---"
Get-Content "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-out.txt" -ErrorAction SilentlyContinue

Write-Output "`nChecking port 1420..."
netstat -ano | Select-String "1420.*LISTENING"

Write-Output "`nRecent node processes (last 2 min):"
Get-CimInstance Win32_Process -Filter "Name='node.exe'" 2>$null | Where-Object { $_.CreationDate -gt (Get-Date).AddMinutes(-2) } | ForEach-Object {
    Write-Output "  PID=$($_.ProcessId) at $($_.CreationDate)"
    if ($_.CommandLine) { Write-Output "    Cmd: $($_.CommandLine)" }
}