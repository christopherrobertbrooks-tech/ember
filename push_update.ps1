param(
    [string]$HostShare = "\\100.100.150.74\Project_Ember"
)

Write-Host "=========================================="
Write-Host "  Ember Auto-Updater (Client -> Host)"
Write-Host "=========================================="
Write-Host "Target Share: $HostShare"
Write-Host "Deploying updated files over Tailscale..."

# Try to verify the share exists before copying
if (-Not (Test-Path $HostShare)) {
    Write-Host "ERROR: Cannot access $HostShare over Tailscale." -ForegroundColor Red
    Write-Host "Please ensure the folder is shared on the HOST computer and the share name is correct." -ForegroundColor Yellow
    Write-Host "Usage: .\push_update.ps1 -HostShare '\\100.100.150.74\YourShareName'"
    exit
}

try {
    Write-Host "Pushing phidata_engine.py..."
    Copy-Item -Path ".\phidata_engine.py" -Destination "$HostShare\phidata_engine.py" -Force

    Write-Host "Pushing manual_tool_parser.py..."
    Copy-Item -Path ".\ember_app\brain\manual_tool_parser.py" -Destination "$HostShare\ember_app\brain\manual_tool_parser.py" -Force

    Write-Host "Pushing researcher.py..."
    Copy-Item -Path ".\agents\researcher.py" -Destination "$HostShare\agents\researcher.py" -Force

    Write-Host "Pushing ember_api.py..."
    Copy-Item -Path ".\ember_api.py" -Destination "$HostShare\ember_api.py" -Force

    Write-Host "Pushing duckduckgo.py..."
    Copy-Item -Path ".\myenv\Lib\site-packages\phi\tools\duckduckgo.py" -Destination "$HostShare\myenv\Lib\site-packages\phi\tools\duckduckgo.py" -Force



    Write-Host ""
    Write-Host "SUCCESS! Core files successfully updated on the Host computer." -ForegroundColor Green
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "ACTION REQUIRED ON HOST:" -ForegroundColor Yellow
    Write-Host "Since the DuckDuckGo tool was upgraded, you still need to open a terminal on your HOST computer (with myenv activated) and run:"
    Write-Host "  pip uninstall -y duckduckgo_search"
    Write-Host "  pip install ddgs"
    Write-Host "=========================================="

} catch {
    Write-Host "Failed to copy files: $_" -ForegroundColor Red
}
