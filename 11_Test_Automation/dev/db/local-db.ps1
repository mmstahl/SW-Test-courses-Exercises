<#
.SYNOPSIS
    Start/stop/check the local, offline Postgres instance used for
    fully-offline local development (see README.md "Fully offline local
    development").

.DESCRIPTION
    Wraps pg_ctl against the portable Postgres binaries extracted for
    this purpose -- no Windows service, no admin rights, just a plain
    background process under your own user account. Reads PGBIN,
    PGDATA_LOCAL, and PGPORT_LOCAL from .env.local in this folder, so
    nothing machine-specific is hardcoded here.

.USAGE
    .\db\local-db.ps1 start
    .\db\local-db.ps1 stop
    .\db\local-db.ps1 status
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "stop", "status")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$envPath = Join-Path $PSScriptRoot "..\.env.local"
if (-not (Test-Path $envPath)) {
    Write-Error ".env.local not found at $envPath -- see README.md's offline setup section."
    exit 1
}

$envVars = @{}
Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
        $envVars[$matches[1]] = $matches[2].Trim()
    }
}

foreach ($key in @("PGBIN", "PGDATA_LOCAL", "PGPORT_LOCAL")) {
    if (-not $envVars.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envVars[$key])) {
        Write-Error "$key is not set in .env.local -- see README.md's offline setup section."
        exit 1
    }
}

$pgCtl = Join-Path $envVars["PGBIN"] "pg_ctl.exe"
$dataDir = $envVars["PGDATA_LOCAL"]
$port = $envVars["PGPORT_LOCAL"]
$logFile = Join-Path (Split-Path $dataDir -Parent) "pglog.txt"

if (-not (Test-Path $pgCtl)) {
    Write-Error "pg_ctl.exe not found at $pgCtl -- check PGBIN in .env.local."
    exit 1
}

switch ($Action) {
    "start" {
        & $pgCtl -D $dataDir -l $logFile -o "-p $port" start
    }
    "stop" {
        & $pgCtl -D $dataDir stop
    }
    "status" {
        & $pgCtl -D $dataDir status
    }
}
