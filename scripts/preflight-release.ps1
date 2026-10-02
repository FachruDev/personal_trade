param(
    [ValidateSet("paper", "live")]
    [string]$Mode = "paper",
    [string]$ProfilePath,
    [string]$EnvPath
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$basePath = Join-Path $projectRoot "freqtrade/config/config.json"
if (-not $EnvPath) {
    $EnvPath = Join-Path $projectRoot ".env"
}
if (-not $ProfilePath) {
    $ProfilePath = Join-Path $projectRoot "freqtrade/config/profiles/$Mode.local.json"
    if (-not (Test-Path -LiteralPath $ProfilePath)) {
        $ProfilePath = Join-Path $projectRoot "freqtrade/config/profiles/$Mode.template.json"
    }
    if (-not (Test-Path -LiteralPath $ProfilePath)) {
        $ProfilePath = Join-Path $projectRoot "freqtrade/config/profiles/paper-conservative.json"
    }
}

if (-not (Test-Path -LiteralPath $basePath) -or -not (Test-Path -LiteralPath $ProfilePath)) {
    throw "Base configuration or selected profile does not exist."
}

$base = Get-Content -LiteralPath $basePath -Raw | ConvertFrom-Json
$profile = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
function Value-OrDefault($name) {
    $value = $profile.PSObject.Properties[$name].Value
    if ($null -ne $value) { return $value }
    return $base.PSObject.Properties[$name].Value
}

function Read-DotEnv($path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $path)) {
        return $values
    }
    foreach ($line in Get-Content -LiteralPath $path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $parts = $line -split '=', 2
        $values[$parts[0].Trim()] = $parts[1]
    }
    return $values
}

function Is-Placeholder($value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return $true }
    $normalized = $value.ToLowerInvariant()
    return $normalized.Contains("replace-with") -or $normalized.Contains("change-me") -or $normalized.Contains("local-development")
}

$errors = [System.Collections.Generic.List[string]]::new()
$dryRun = [bool](Value-OrDefault "dry_run")
$maxOpenTrades = [int](Value-OrDefault "max_open_trades")
$tradableBalanceRatio = [double](Value-OrDefault "tradable_balance_ratio")
$orderTypes = Value-OrDefault "order_types"

if ($Mode -eq "paper") {
    if (-not $dryRun) { $errors.Add("Paper profile must keep dry_run=true.") }
    if ($maxOpenTrades -gt 1) { $errors.Add("Paper profile must allow at most one open trade.") }
    if ($tradableBalanceRatio -gt 0.25) { $errors.Add("Paper profile must cap tradable_balance_ratio at 0.25.") }
}
else {
    if ($dryRun) { $errors.Add("Live profile must explicitly set dry_run=false.") }
    if ($maxOpenTrades -gt 1) { $errors.Add("Live profile must allow at most one open trade during the limited release.") }
    if ($tradableBalanceRatio -gt 0.10) { $errors.Add("Live profile must cap tradable_balance_ratio at 0.10 during the limited release.") }
    if ($null -eq $orderTypes -or -not [bool]$orderTypes.stoploss_on_exchange) { $errors.Add("Live profile must enable stoploss_on_exchange.") }

    if ((Split-Path -Leaf $ProfilePath) -eq "live.template.json") { $errors.Add("Live release must use an ignored live.local.json profile, not live.template.json.") }
    $environment = Read-DotEnv $EnvPath
    if ($environment["TRADING_ENVIRONMENT"] -ne "live") { $errors.Add("Live release environment must set TRADING_ENVIRONMENT=live.") }
    foreach ($name in @("BINANCE_API_KEY", "BINANCE_API_SECRET", "BOT_CONTROL_TOKEN", "FREQTRADE_API_PASSWORD", "FREQTRADE_JWT_SECRET")) {
        if (Is-Placeholder $environment[$name]) { $errors.Add("Live release requires a non-placeholder $name in the selected .env file.") }
    }
    $approvalPath = $environment["LIVE_RELEASE_APPROVAL_FILE"]
    if ([string]::IsNullOrWhiteSpace($approvalPath)) {
        $errors.Add("Live release requires LIVE_RELEASE_APPROVAL_FILE.")
    }
    elseif (-not (Test-Path -LiteralPath $approvalPath)) {
        $errors.Add("Live release approval record does not exist.")
    }
    else {
        try { $approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json }
        catch { $errors.Add("Live release approval record is not valid JSON."); $approval = $null }
        if ($null -ne $approval) {
            if ($approval.acknowledgement -ne "LIMITED_LIVE_APPROVED") { $errors.Add("Live release approval acknowledgement is missing.") }
            foreach ($name in @("approved_at", "owner", "strategy_revision", "quant_report_sha256", "paper_run_end")) {
                if ([string]::IsNullOrWhiteSpace([string]$approval.$name)) { $errors.Add("Live release approval requires $name.") }
            }
            if ([string]$approval.quant_report_sha256 -notmatch '^[a-fA-F0-9]{64}$') { $errors.Add("Live release approval requires a SHA-256 quant report digest.") }
        }
    }
}

if ($errors.Count -gt 0) {
    throw ($errors -join " ")
}

[pscustomobject]@{
    mode = $Mode
    profile = (Resolve-Path -LiteralPath $ProfilePath).Path
    dry_run = $dryRun
    max_open_trades = $maxOpenTrades
    tradable_balance_ratio = $tradableBalanceRatio
    stoploss_on_exchange = if ($null -eq $orderTypes) { $null } else { [bool]$orderTypes.stoploss_on_exchange }
} | ConvertTo-Json
