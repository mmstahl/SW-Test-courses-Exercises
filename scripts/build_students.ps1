$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if ([string]::IsNullOrWhiteSpace($env:BUILD_TARGET)) {
    $env:BUILD_TARGET = "all"
}

docker compose run --build --rm sandbox
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose build jupyter
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose up -d jupyter
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose ps
