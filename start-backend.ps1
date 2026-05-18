$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:BILITOOLS_PLUS_ROOT) { $env:BILITOOLS_PLUS_ROOT = $root }
$env:PYTHONPATH = $root
$port = if ($env:BILITOOLS_PORT) { $env:BILITOOLS_PORT } elseif ($env:PORT) { $env:PORT } else { "8001" }
$env:PORT = $port
cd $root
$proc = Start-Process -FilePath python -ArgumentList '-m app.main' -PassThru -WindowStyle Hidden
Write-Output "PID: $($proc.Id)"
Start-Sleep -Seconds 6
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
    Write-Output $r.Content
} catch {
    Write-Output "FAILED: $($_.Exception.Message)"
}
