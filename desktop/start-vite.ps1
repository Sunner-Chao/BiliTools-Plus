$env:MODE = "electron"
$env:PYTHONPATH = "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus"
$env:NODE_OPTIONS = "--max-old-space-size=4096"

Write-Output "Starting vite with MODE=$env:MODE"
Write-Output "Working directory: $(Get-Location)"
Write-Output "Node version: $(node --version)"
Write-Output "Vite version: $(vite --version)"

# Run vite directly in the current process (not via Start-Process)
# This ensures environment variables are properly inherited
Set-Location "D:\pro_sunner\demo_vscode\Bili-Tools\BiliTools-Plus\desktop"
npm run dev:electron