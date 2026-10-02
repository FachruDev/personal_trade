param(
    [int[]]$Lookbacks = @(10, 20)
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
    foreach ($lookback in $Lookbacks) {
        $className = "RegimeRiskBreakout$lookback"
        $indicator = "        dataframe[`"prior_high`"] = dataframe[`"high`"].rolling($lookback).max().shift(1)"
        $conditionReplacement = "            & (dataframe[`"close`"] > dataframe[`"prior_high`"])`n            & (dataframe[`"volume`"] > dataframe[`"volume_sma`"])"
        $experimentStrategy = $baseStrategy.Replace("class RegimeRiskStrategy", "class $className").Replace('        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)', "        dataframe[`"atr`"] = ta.ATR(dataframe, timeperiod=14)`n$indicator").Replace('            & (dataframe["volume"] > dataframe["volume_sma"])', $conditionReplacement)
        Set-Content -LiteralPath (Join-Path $experimentPath "$className.py") -Value $experimentStrategy -NoNewline

        foreach ($period in $periods) {
            & docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy $className --strategy-path /freqtrade/user_data/strategies/.experiments --timeframe 1h --timerange $period.Range
            if ($LASTEXITCODE -ne 0) {
                throw "Breakout $lookback $($period.Name) backtest failed."
            }
            $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            Copy-Item -LiteralPath $latest.FullName -Destination (Join-Path $resultPath "breakout$($lookback)_$($period.Name).zip") -Force
        }
    }
}
finally {
    Remove-Item -LiteralPath $experimentPath -Recurse -Force -ErrorAction SilentlyContinue
}
