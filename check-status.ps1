$allNode = Get-Process -Name 'node' -ErrorAction SilentlyContinue
$allNode | Format-Table Id, StartTime -AutoSize
$cmdProc = Get-Process -Id 46360 -ErrorAction SilentlyContinue
if ($cmdProc) {
    Write-Output "CMD process still running: $($cmdProc.Id)"
} else {
    Write-Output "CMD process (46360) has exited"
}
$backendProc = Get-Process -Id 4704 -ErrorAction SilentlyContinue
if ($backendProc) {
    Write-Output "Backend still running: $($backendProc.Id)"
}
Write-Output "Checking port 1420..."
netstat -ano | Select-String "1420"