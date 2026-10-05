param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_]*$')]
    [string]$Strategy,
    [string]$Timerange = "20231013-20261002",
    [int[]]$StartupCandles = @(1000, 1400, 1800)
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$containerResultDirectory = "/freqtrade/user_data/backtest_results"
$lookaheadResult = "$containerResultDirectory/$Strategy-lookahead.csv"
$hostLookaheadResult = Join-Path $projectRoot "freqtrade/backtest_results/$Strategy-lookahead.csv"

# Freqtrade 2026.9 can fail while updating an existing mixed-type CSV with
# recent pandas versions. This is generated evidence, so each run must start
# with a fresh export rather than reusing an old report.
if (Test-Path -LiteralPath $hostLookaheadResult) {
    Remove-Item -LiteralPath $hostLookaheadResult -Force
}

& docker compose --env-file .env.example run --rm --no-deps freqtrade freqtrade lookahead-analysis `
    --config /freqtrade/user_data/config.json `
    --strategy $Strategy `
    --strategy-path /freqtrade/user_data/strategies `
    --timeframe 1h `
    --timerange $Timerange `
    --minimum-trade-amount 1 `
    --targeted-trade-amount 20 `
    --lookahead-analysis-exportfilename $lookaheadResult
if ($LASTEXITCODE -ne 0) {
    throw "Look-ahead analysis failed for $Strategy."
}

& docker compose --env-file .env.example run --rm --no-deps freqtrade freqtrade recursive-analysis `
    --config /freqtrade/user_data/config.json `
    --strategy $Strategy `
    --strategy-path /freqtrade/user_data/strategies `
    --timeframe 1h `
    --timerange $Timerange `
    --startup-candle $StartupCandles
if ($LASTEXITCODE -ne 0) {
    throw "Recursive analysis failed for $Strategy."
}

Write-Output "Strategy integrity checks completed for $Strategy. Look-ahead output: $lookaheadResult"
