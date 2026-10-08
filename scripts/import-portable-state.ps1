param(
    [Parameter(Mandatory)]
    [string]$Source,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $Force) {
    throw "Restoring replaces the target PostgreSQL application data. Re-run with -Force only on a prepared VPS."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$manifestPath = Join-Path $sourcePath "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Portable-state manifest.json was not found."
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.format -ne "trading-bot-portable-state/v1") {
    throw "Unsupported portable-state format."
}
$dumpPath = Join-Path $sourcePath $manifest.postgres_dump
if (-not (Test-Path -LiteralPath $dumpPath)) {
    throw "PostgreSQL dump referenced by the manifest was not found."
}

foreach ($service in @("api", "web", "freqtrade")) {
    # `docker compose ps` prints nothing for a stopped service; -join turns that null into an empty string.
    $running = ((& docker compose ps --status running -q $service) -join "").Trim()
    if (-not [string]::IsNullOrWhiteSpace($running)) {
        throw "Stop the running $service service before restoring portable state."
    }
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed."
    }
}

Invoke-Compose @("up", "-d", "postgres", "redis")
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    & docker compose exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
    if ($attempt -eq 29) { throw "PostgreSQL did not become ready for restore." }
}

$postgresId = (& docker compose ps -q postgres).Trim()
if ([string]::IsNullOrWhiteSpace($postgresId)) {
    throw "PostgreSQL container is unavailable."
}
& docker cp $dumpPath "$postgresId`:/tmp/trading-bot-portable-state.dump"
if ($LASTEXITCODE -ne 0) {
    throw "Could not copy the PostgreSQL portable-state archive into the container."
}
Invoke-Compose @("exec", "-T", "postgres", "sh", "-lc", 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/trading-bot-portable-state.dump')
Invoke-Compose @("exec", "-T", "postgres", "rm", "-f", "/tmp/trading-bot-portable-state.dump")

$tradeFiles = @($manifest.freqtrade_trade_files)
foreach ($relative in $tradeFiles) {
    $sourceFile = Join-Path $sourcePath $relative
    $targetFile = Join-Path $projectRoot (Join-Path "freqtrade" ($relative -replace '^freqtrade[\\/]', ''))
    if (-not (Test-Path -LiteralPath $sourceFile)) {
        throw "Freqtrade trade file listed in manifest is missing: $relative"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetFile) | Out-Null
    # A stale -wal/-shm left by an earlier database would be replayed onto the restored file and corrupt it.
    Remove-Item -LiteralPath "$targetFile-wal", "$targetFile-shm" -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force
}

[pscustomobject]@{
    restored_postgres_dump = $manifest.postgres_dump
    restored_freqtrade_trade_files = $tradeFiles.Count
    next_step = "Copy .env securely, then run: docker compose up -d"
} | ConvertTo-Json
