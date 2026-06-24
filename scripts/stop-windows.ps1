$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\.."
docker compose down
Write-Host "App stopped."
Pop-Location
