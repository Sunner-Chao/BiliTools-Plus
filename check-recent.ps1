$procs = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" 2>$null)
$startTime = (Get-Date).AddMinutes(-5)
$recentProcs = $procs | Where-Object {
    $ts = $_.CreationDate
    return $ts -and $ts -gt $startTime
}
Write-Output "Recent node processes (last 5 min):"
foreach ($p in $recentProcs) {
    Write-Output "  PID $($p.ProcessId) started $($p.CreationDate)"
    if ($p.CommandLine) {
        Write-Output "    $($p.CommandLine)"
    }
}