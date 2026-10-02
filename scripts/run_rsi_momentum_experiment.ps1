param(
    [int[]]$RsiMinimums = @(50, 55)
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
    foreach ($rsiMinimum in $RsiMinimums) {
        $className = "RegimeRiskRsi$rsiMinimum"
        $experimentStrategy = $baseStrategy.Replace("class RegimeRiskStrategy", "class $className").Replace('dataframe["rsi"].between(45, 65)', "dataframe[`"rsi`"].between($rsiMinimum, 65)")
        Set-Content -LiteralPath (Join-Path $experimentPath "$className.py") -Value $experimentStrategy -NoNewline

        foreach ($period in $periods) {
            & docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy $className --strategy-path /freqtrade/user_data/strategies/.experiments --timeframe 1h --timerange $period.Range
            if ($LASTEXITCODE -ne 0) {
                throw "RSI $rsiMinimum $($period.Name) backtest failed."
            }
            $latest = Get-ChildItem -LiteralPath $resultPath -Filter "*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            Copy-Item -LiteralPath $latest.FullName -Destination (Join-Path $resultPath "rsi$($rsiMinimum)_$($period.Name).zip") -Force
        }
    }
}
finally {
    Remove-Item -LiteralPath $experimentPath -Recurse -Force -ErrorAction SilentlyContinue
}
