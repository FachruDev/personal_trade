param(
    [switch]$SkipDownload,
    # paper = the 25% paper profile; full = research profile with 99% of the wallet deployed.
    [ValidateSet("paper", "full")]
    [string]$Deployment = "paper",
    # Backtests ignore protections unless enabled; use this switch to measure the circuit breaker's effect.
    [switch]$NoProtections
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $projectRoot "freqtrade/backtest_results"
$profile = if ($Deployment -eq "full") { "/freqtrade/user_data/config/profiles/research-daily-trend-full.json" } else { "/freqtrade/user_data/config/profiles/paper-daily-trend.json" }
[string[]]$protectionArgs = if ($NoProtections) { @() } else { @("--enable-protections") }
$label = "$Deployment" + $(if ($NoProtections) { "_noprot" } else { "" })

# Periods are reporting segments only. The strategy has no fitted parameters, so these are not
# development/validation splits; see docs/daily-trend-validation.md.
$periods = @(
    @{ Name = "full"; Range = "20180401-" },
    @{ Name = "2018_2021"; Range = "20180401-20220101" },
    @{ Name = "2022_2023"; Range = "20220101-20240101" },
    @{ Name = "2024_onward"; Range = "20240101-" }
)

Push-Location $projectRoot
try {
    if (-not $SkipDownload) {
        & docker compose --env-file .env.example run --rm --no-deps freqtrade freqtrade download-data `
            --config /freqtrade/user_data/config.json `
            --pairs BTC/USDT ETH/USDT --timeframes 1d --timerange 20170801-
        if ($LASTEXITCODE -ne 0) {
            throw "Daily candle download failed."
        }
    }

    foreach ($period in $periods) {
        # --no-deps: backtests must not need the API; the strategy skips the kill-switch outside dry-run/live.
        & docker compose --env-file .env.example run --rm --no-deps freqtrade freqtrade backtesting `
            --config /freqtrade/user_data/config.json `
            --config $profile `
            --strategy DailyTrendVolStrategy `
            --strategy-path /freqtrade/user_data/strategies `
            --timeframe 1d `
            --timerange $period.Range `
            --cache none `
            @protectionArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Daily trend $($period.Name) backtest failed."
        }
        $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        Copy-Item -LiteralPath $latest.FullName -Destination (Join-Path $resultPath "daily_trend_$($label)_$($period.Name).zip") -Force
    }
}
finally {
    Pop-Location
}
