$env:MODE = "electron"
$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"

Write-Output "Working directory: $(Get-Location)"
Write-Output "NODE version: $(node --version)"
Write-Output "NPM version: $(npm --version)"
Write-Output "Running: npm run dev:electron"
Write-Output "Mode env var: $env:MODE"

# Run npm directly, capture output
$npmProc = Start-Process -FilePath "npm" -ArgumentList "run", "dev:electron" -WorkingDirectory "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop" -PassThru -RedirectStandardOutput "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-out.txt" -RedirectStandardError "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-err.txt"
Write-Output "NPM PID: $($npmProc.Id)"
Start-Sleep -Seconds 10

Write-Output "`n--- NPM stdout ---"
Get-Content "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-out.txt" -ErrorAction SilentlyContinue
Write-Output "`n--- NPM stderr ---"
Get-Content "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop\npm-err.txt" -ErrorAction SilentlyContinue
Write-Output "`nNPM Process:"
$npmProc | Select-Object Id, HasExited, ExitCode

Write-Output "`nChecking port 1420..."
netstat -ano | Select-String "1420.*LISTENING"

Write-Output "`nRecent node processes:"
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CreationDate -gt (Get-Date).AddMinutes(-2) } | ForEach-Object {
    Write-Output "  PID=$($_.ProcessId) at $($_.CreationDate)"
    if ($_.CommandLine) { Write-Output "    Cmd: $($_.CommandLine)" }
}