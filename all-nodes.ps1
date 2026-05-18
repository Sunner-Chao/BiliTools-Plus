$allNode = Get-CimInstance Win32_Process -Filter "Name='node.exe'" 2>$null
$recent = $allNode | Where-Object { $_.CreationDate -gt (Get-Date).AddMinutes(-30) }
Write-Output "Node processes started in last 30 minutes ($($recent.Count)):"
foreach ($p in $recent) {
    Write-Output "  PID=$($p.ProcessId) at $($p.CreationDate)"
    Write-Output "    Cmd: $($p.CommandLine)"
}

Write-Output "`nAll node PIDs:"
$allNode | ForEach-Object { Write-Output "  $($_.ProcessId) -> $($_.CreationDate) -> $($_.CommandLine -replace '`n',' ' -replace '`r',' ')" }