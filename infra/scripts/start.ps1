# Bootstrap + start the full local stack (Windows PowerShell).
# Usage: ./infra/scripts/start.ps1
$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RootDir

if (-not (Test-Path ".env")) {
    Write-Host "-> No .env found, creating one from .env.example"
    Copy-Item ".env.example" ".env"
}

Write-Host "-> Building and starting containers..."
docker compose up --build -d

Write-Host "-> Waiting for backend health endpoint..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing http://localhost:8000/health -TimeoutSec 2 | Out-Null
        Write-Host "OK  Backend healthy at http://localhost:8000"
        Write-Host "OK  API docs at        http://localhost:8000/docs"
        exit 0
    } catch {
        Start-Sleep -Seconds 2
    }
}

Write-Host "FAIL Backend did not become healthy. Check: docker compose logs backend"
exit 1
