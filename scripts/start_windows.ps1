$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$ImageName = "finally-app"
$ContainerName = "finally-app"

$imageExists = docker image inspect $ImageName *>$null; $?
if ($args -contains "--build" -or -not $imageExists) {
    Write-Host "Building Docker image..."
    docker build -t $ImageName .
}

$existing = docker ps -a --format "{{.Names}}" | Select-String -Pattern "^$ContainerName$"
if ($existing) {
    Write-Host "Removing existing container..."
    docker rm -f $ContainerName | Out-Null
}

New-Item -ItemType Directory -Force -Path "db" | Out-Null

docker run -d `
    --name $ContainerName `
    -v "${PWD}\db:/app/db" `
    -p 8000:8000 `
    --env-file .env `
    $ImageName

Write-Host "FinAlly is running at http://localhost:8000"
