param(
    [int[]]$Hours = @(24, 48)
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$strategyRoot = Join-Path $projectRoot "freqtrade/strategies"
$sourcePath = Join-Path $strategyRoot "RegimeRiskStrategy.py"
$experimentPath = Join-Path $strategyRoot ".experiments"
$resultPath = Join-Path $projectRoot "freqtrade/backtest_results"
$periods = @(
    @{ Name = "development"; Range = "20231013-20251001" },
    @{ Name = "validation"; Range = "20251001-20260401" },
    @{ Name = "out_of_sample"; Range = "20260401-20261002" }
)

New-Item -ItemType Directory -Path $experimentPath -Force | Out-Null

try {
    $baseStrategy = Get-Content -LiteralPath $sourcePath -Raw
    foreach ($hour in $Hours) {
        $className = "RegimeRiskTimeStop$hour"
        $timeStop = @"
        if current_time - trade.open_date_utc >= timedelta(hours=$hour) and current_profit <= 0:
            return "time_stop_loss"
        return None
"@.TrimEnd()
        $exitTail = @"
            return "take_profit_2"
        return None
"@.TrimEnd()
        $replacementTail = @"
            return "take_profit_2"
$timeStop
"@.TrimEnd()
        $experimentStrategy = $baseStrategy.Replace('from datetime import datetime', 'from datetime import datetime, timedelta').Replace("class RegimeRiskStrategy", "class $className").Replace($exitTail, $replacementTail)
        Set-Content -LiteralPath (Join-Path $experimentPath "$className.py") -Value $experimentStrategy -NoNewline

        foreach ($period in $periods) {
            & docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy $className --strategy-path /freqtrade/user_data/strategies/.experiments --timeframe 1h --timerange $period.Range
            if ($LASTEXITCODE -ne 0) {
                throw "Time stop $hour $($period.Name) backtest failed."
            }
            $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            Copy-Item -LiteralPath $latest.FullName -Destination (Join-Path $resultPath "timestop$($hour)_$($period.Name).zip") -Force
        }
    }
}
finally {
    Remove-Item -LiteralPath $experimentPath -Recurse -Force -ErrorAction SilentlyContinue
}
