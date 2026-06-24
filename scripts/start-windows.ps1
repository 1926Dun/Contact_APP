$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\.."
docker compose up --build -d
Write-Host "App running at http://localhost:8000"
Pop-Location
