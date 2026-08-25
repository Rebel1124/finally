$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"

$existing = docker ps -a --format "{{.Names}}" | Select-String -Pattern "^$ContainerName$"
if ($existing) {
    docker rm -f $ContainerName | Out-Null
    Write-Host "Stopped and removed $ContainerName"
} else {
    Write-Host "$ContainerName is not running"
}
