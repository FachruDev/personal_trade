param(
    [Parameter(Mandatory)]
    [string]$Label,
    [Parameter(Mandatory)]
    [string]$Strategy,
    [string]$StrategyPath = "/freqtrade/user_data/strategies"
)

# This is a fixed-parameter protocol. It deliberately does not optimize or
# select parameters between folds. The five 6-month windows are frozen against
# the historical BTC/ETH dataset available on 2 October 2026.
$projectRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $projectRoot "freqtrade/backtest_results"
$periods = @(
    @{ Name = "forward_2024h1"; Range = "20240401-20241001" },
    @{ Name = "forward_2024h2"; Range = "20241001-20250401" },
    @{ Name = "forward_2025h1"; Range = "20250401-20251001" },
    @{ Name = "forward_2025h2"; Range = "20251001-20260401" },
    @{ Name = "forward_2026h1"; Range = "20260401-20261002" }
)

$artifacts = @()
foreach ($period in $periods) {
    & docker compose --env-file .env.example run --rm --no-deps freqtrade freqtrade backtesting `
        --config /freqtrade/user_data/config.json `
        --strategy $Strategy `
        --strategy-path $StrategyPath `
        --timeframe 1h `
        --timerange $period.Range
    if ($LASTEXITCODE -ne 0) {
        throw "Walk-forward backtest $($period.Name) failed."
    }
    $target = Join-Path $resultPath "$Label`_$($period.Name).zip"
    $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Copy-Item -LiteralPath $latest.FullName -Destination $target -Force
    $artifacts += "--artifact"
    $artifacts += "$($period.Name)=$target"
}

& C:\Python314\python.exe (Join-Path $PSScriptRoot "evaluate_walk_forward_gates.py") `
    --label $Label `
    @artifacts `
    --output (Join-Path $projectRoot "docs/quant-reports/$Label-walk-forward.json")
exit $LASTEXITCODE
