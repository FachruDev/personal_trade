$projectRoot = Split-Path -Parent $PSScriptRoot
$strategyRoot = Join-Path $projectRoot "freqtrade/strategies"
$sourcePath = Join-Path $strategyRoot "RegimeRiskStrategy.py"
$experimentPath = Join-Path $strategyRoot ".experiments"
$resultPath = Join-Path $projectRoot "freqtrade/backtest_results"
$className = "RegimeRiskStructureBreakout20"
$periods = @(
    @{ Name = "development"; Range = "20231013-20251001" },
    @{ Name = "validation"; Range = "20251001-20260401" },
    @{ Name = "out_of_sample"; Range = "20260401-20261002" }
)

New-Item -ItemType Directory -Path $experimentPath -Force | Out-Null

try {
    $baseStrategy = Get-Content -LiteralPath $sourcePath -Raw
    $structureIndicators = @"
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["higher_high"] = dataframe["high"] > dataframe["high"].shift(1)
        dataframe["higher_low"] = dataframe["low"] > dataframe["low"].shift(1)
"@.TrimEnd()
    $mainIndicators = @"
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["prior_high"] = dataframe["high"].rolling(20).max().shift(1)
"@.TrimEnd()
    $condition = @"
            & dataframe["higher_high_4h"].fillna(False)
            & dataframe["higher_low_4h"].fillna(False)
            & (dataframe["close"] > dataframe["prior_high"])
            & (dataframe["volume"] > dataframe["volume_sma"])
"@.TrimEnd()
    $experimentStrategy = $baseStrategy.Replace("class RegimeRiskStrategy", "class $className").Replace('        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]', $structureIndicators).Replace('        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)', $mainIndicators).Replace('            & (dataframe["volume"] > dataframe["volume_sma"])', $condition)
    Set-Content -LiteralPath (Join-Path $experimentPath "$className.py") -Value $experimentStrategy -NoNewline

    foreach ($period in $periods) {
        & docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy $className --strategy-path /freqtrade/user_data/strategies/.experiments --timeframe 1h --timerange $period.Range
        if ($LASTEXITCODE -ne 0) {
            throw "Composite entry quality $($period.Name) backtest failed."
        }
        $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        Copy-Item -LiteralPath $latest.FullName -Destination (Join-Path $resultPath "structure_breakout20_$($period.Name).zip") -Force
    }
}
finally {
    Remove-Item -LiteralPath $experimentPath -Recurse -Force -ErrorAction SilentlyContinue
}
