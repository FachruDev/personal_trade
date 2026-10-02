param(
    [Parameter(Mandatory)]
    [string]$Label,
    [Parameter(Mandatory)]
    [string]$Development,
    [Parameter(Mandatory)]
    [string]$Validation,
    [Parameter(Mandatory)]
    [string]$OutOfSample
)

$projectRoot = Split-Path -Parent $PSScriptRoot
& C:\Python314\python.exe (Join-Path $PSScriptRoot "evaluate_backtest_gates.py") `
    --label $Label `
    --development (Join-Path $projectRoot $Development) `
    --validation (Join-Path $projectRoot $Validation) `
    --out-of-sample (Join-Path $projectRoot $OutOfSample) `
    --output (Join-Path $projectRoot "docs/quant-reports/$Label.json")
exit $LASTEXITCODE
