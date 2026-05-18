$procs = Get-CimInstance Win32_Process -Filter "ProcessId=22500 OR ProcessId=26536 OR ProcessId=38224 OR ProcessId=8132"
foreach ($p in $procs) {
    Write-Output "PID $($p.ProcessId): $($p.Name)"
    if ($p.CommandLine) {
        Write-Output "  Cmd: $($p.CommandLine.Substring(0, [Math]::Min(250, $p.CommandLine.Length)))"
    }
}