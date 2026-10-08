param(
    [string]$Destination = "",
    [switch]$IncludeHistoricalData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $projectRoot "portable-state"
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed."
    }
}

$postgresId = (& docker compose ps -q postgres).Trim()
if ([string]::IsNullOrWhiteSpace($postgresId)) {
    throw "The PostgreSQL container is not running. Start the stack before exporting portable state."
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$timestamp = [DateTimeOffset]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$dumpName = "trading-bot-postgres-$timestamp.dump"
$dumpPath = Join-Path $Destination $dumpName

# A custom pg_dump archive preserves every audit/context table while keeping
# database credentials out of the archive. The .env file is never copied.
Invoke-Compose @("exec", "-T", "postgres", "sh", "-lc", 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file=/tmp/trading-bot-portable-state.dump')
& docker cp "$postgresId`:/tmp/trading-bot-portable-state.dump" $dumpPath
if ($LASTEXITCODE -ne 0) {
    throw "Could not copy the PostgreSQL portable-state archive."
}
Invoke-Compose @("exec", "-T", "postgres", "rm", "-f", "/tmp/trading-bot-portable-state.dump")

$copiedTradeFiles = @()
$freqtradeRoot = Join-Path $projectRoot "freqtrade"
$tradeDestination = Join-Path $Destination "freqtrade"
$freqtradeRunning = -not [string]::IsNullOrWhiteSpace(((& docker compose ps --status running -q freqtrade) -join "").Trim())
if ($freqtradeRunning) {
    # Online snapshot through SQLite's backup API: a plain copy of a live WAL database can be torn.
    $snapshotScript = @'
import glob
import os
import sqlite3

for source in glob.glob("/freqtrade/user_data/**/*.sqlite", recursive=True):
    name = os.path.basename(source)
    if name.startswith(".export-"):
        continue
    target = os.path.join(os.path.dirname(source), ".export-" + name)
    reader = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    writer = sqlite3.connect(target)
    reader.backup(writer)
    writer.close()
    reader.close()
'@
    $snapshotScript | & docker compose exec -T freqtrade python -
    if ($LASTEXITCODE -ne 0) {
        throw "Could not snapshot the Freqtrade trade database."
    }
    Get-ChildItem -LiteralPath $freqtradeRoot -File -Recurse -Force |
        Where-Object { $_.Name -like ".export-*.sqlite" } |
        ForEach-Object {
            $relative = $_.FullName.Substring($freqtradeRoot.Length).TrimStart('\', '/') -replace '(^|[\\/])\.export-', '$1'
            $target = Join-Path $tradeDestination $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
            $copiedTradeFiles += (Join-Path "freqtrade" $relative).Replace('\', '/')
        }
    & docker compose exec -T freqtrade sh -c 'find /freqtrade/user_data -type f -name ".export-*.sqlite" -delete'
}
elseif (Test-Path -LiteralPath $freqtradeRoot) {
    Get-ChildItem -LiteralPath $freqtradeRoot -File -Recurse |
        Where-Object { $_.Name -like "*.sqlite*" -and $_.Name -notlike ".export-*" } |
        ForEach-Object {
            $relative = $_.FullName.Substring($freqtradeRoot.Length).TrimStart('\', '/')
            $target = Join-Path $tradeDestination $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
            $copiedTradeFiles += (Join-Path "freqtrade" $relative).Replace('\', '/')
        }
}

if ($IncludeHistoricalData) {
    $historicalSource = Join-Path $freqtradeRoot "data"
    if (Test-Path -LiteralPath $historicalSource) {
        Copy-Item -LiteralPath $historicalSource -Destination $tradeDestination -Recurse -Force
    }
}

$paperRun = $null
try {
    $paperRun = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/paper-run" -TimeoutSec 5
}
catch {
    # The database dump remains valid even when the local API is stopped.
}

$gitRevision = $null
try {
    $gitRevision = (& git -C $projectRoot rev-parse HEAD 2>$null).Trim()
}
catch {}

$manifest = [ordered]@{
    format = "trading-bot-portable-state/v1"
    created_at = [DateTimeOffset]::UtcNow.ToString("o")
    postgres_dump = $dumpName
    freqtrade_trade_files = $copiedTradeFiles
    historical_data_included = [bool]$IncludeHistoricalData
    source_revision = $gitRevision
    paper_run = $paperRun
    secrets_included = $false
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Destination "manifest.json") -Encoding utf8

[pscustomobject]@{
    destination = (Resolve-Path -LiteralPath $Destination).Path
    postgres_dump = $dumpName
    copied_freqtrade_trade_files = $copiedTradeFiles.Count
    historical_data_included = [bool]$IncludeHistoricalData
    secrets_included = $false
} | ConvertTo-Json
