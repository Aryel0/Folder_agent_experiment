# PowerShell build script for agent sandbox Docker image
param (
    [string]$Tag = "agent-sandbox:latest"
)

Write-Host "Building Docker sandbox image: $Tag..." -ForegroundColor Cyan
docker build -t $Tag -f docker/Dockerfile.sandbox .

if ($LASTEXITCODE -eq 0) {
    Write-Host "Docker sandbox image built successfully!" -ForegroundColor Green
} else {
    Write-Host "Docker build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
