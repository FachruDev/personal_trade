param(
    [ValidateSet("paper", "live")]
    [string]$Mode = "paper",
    [string]$ProfilePath,
    [string]$EnvPath,
    # Paper-only override for multi-pair strategies (for example the daily trend candidate, which
    # trades BTC and ETH together). The live release limit stays at one open trade.
    [ValidateRange(1, 2)]
    [int]$PaperMaxOpenTrades = 1
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
$clockDriftSeconds = $null
$dryRun = [bool](Value-OrDefault "dry_run")
$maxOpenTrades = [int](Value-OrDefault "max_open_trades")
$tradableBalanceRatio = [double](Value-OrDefault "tradable_balance_ratio")
$orderTypes = Value-OrDefault "order_types"

if ($Mode -eq "paper") {
    if (-not $dryRun) { $errors.Add("Paper profile must keep dry_run=true.") }
    if ($maxOpenTrades -gt $PaperMaxOpenTrades) { $errors.Add("Paper profile must allow at most $PaperMaxOpenTrades open trade(s); pass -PaperMaxOpenTrades for a multi-pair strategy.") }
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

    $binanceBaseUrl = $environment["BINANCE_PUBLIC_BASE_URL"]
    if ([string]::IsNullOrWhiteSpace($binanceBaseUrl)) { $binanceBaseUrl = "https://api.binance.com" }
    try {
        $binanceTime = Invoke-RestMethod -Uri "$($binanceBaseUrl.TrimEnd('/'))/api/v3/time" -TimeoutSec 10
        if ($null -eq $binanceTime.serverTime) { throw "Response does not contain serverTime." }
        $clockDriftSeconds = [math]::Abs(([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() - [double]$binanceTime.serverTime) / 1000)
        if ($clockDriftSeconds -gt 2) {
            $errors.Add(("Host clock drift versus Binance is {0:N3} seconds; synchronize the host clock before live release." -f $clockDriftSeconds))
        }
    }
    catch {
        $errors.Add("Live release could not verify Binance server time: $($_.Exception.Message)")
    }

    $approvalPath = $environment["LIVE_RELEASE_APPROVAL_FILE"]
    $approval = $null
    if ([string]::IsNullOrWhiteSpace($approvalPath)) {
        $errors.Add("Live release requires LIVE_RELEASE_APPROVAL_FILE.")
    }
    $approvalHostPath = $approvalPath
    $containerPrefix = "/freqtrade/user_data/"
    if (-not [string]::IsNullOrWhiteSpace($approvalPath) -and $approvalPath.StartsWith($containerPrefix)) {
        $relativePath = $approvalPath.Substring($containerPrefix.Length).Replace("/", [IO.Path]::DirectorySeparatorChar)
        $approvalHostPath = Join-Path $projectRoot "freqtrade/$relativePath"
    }
    if (-not [string]::IsNullOrWhiteSpace($approvalPath) -and -not (Test-Path -LiteralPath $approvalHostPath)) {
        $errors.Add("Live release approval record does not exist.")
    }
    elseif (-not [string]::IsNullOrWhiteSpace($approvalPath)) {
        try { $approval = Get-Content -LiteralPath $approvalHostPath -Raw | ConvertFrom-Json }
        catch { $errors.Add("Live release approval record is not valid JSON."); $approval = $null }
        if ($null -ne $approval) {
            if ($approval.acknowledgement -ne "LIMITED_LIVE_APPROVED") { $errors.Add("Live release approval acknowledgement is missing.") }
            foreach ($name in @("approved_at", "owner", "strategy_revision", "strategy_source_sha256", "quant_report_sha256", "paper_run_end")) {
                if ([string]::IsNullOrWhiteSpace([string]$approval.$name)) { $errors.Add("Live release approval requires $name.") }
            }
            if ([string]$approval.quant_report_sha256 -notmatch '^[a-fA-F0-9]{64}$') { $errors.Add("Live release approval requires a SHA-256 quant report digest.") }
            if ([string]$approval.strategy_source_sha256 -notmatch '^[a-fA-F0-9]{64}$') { $errors.Add("Live release approval requires a SHA-256 strategy source digest.") }
        }
    }

    $strategySourcePath = $environment["FREQTRADE_STRATEGY_SOURCE_FILE"]
    if ([string]::IsNullOrWhiteSpace($strategySourcePath)) {
        $errors.Add("Live release requires FREQTRADE_STRATEGY_SOURCE_FILE.")
    }
    else {
        $strategySourceHostPath = $strategySourcePath
        if ($strategySourcePath.StartsWith($containerPrefix)) {
            $relativePath = $strategySourcePath.Substring($containerPrefix.Length).Replace("/", [IO.Path]::DirectorySeparatorChar)
            $strategySourceHostPath = Join-Path $projectRoot "freqtrade/$relativePath"
        }
        if (-not (Test-Path -LiteralPath $strategySourceHostPath)) {
            $errors.Add("Live strategy source file does not exist.")
        }
        elseif ($null -ne $approval) {
            $strategyDigest = (Get-FileHash -LiteralPath $strategySourceHostPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($strategyDigest -ne [string]$approval.strategy_source_sha256.ToLowerInvariant()) {
                $errors.Add("Live strategy source SHA-256 does not match the approval record.")
            }
        }
    }

    $quantReportPath = $environment["LIVE_QUANT_REPORT_FILE"]
    if ([string]::IsNullOrWhiteSpace($quantReportPath)) {
        $errors.Add("Live release requires LIVE_QUANT_REPORT_FILE.")
    }
    else {
        $quantReportHostPath = $quantReportPath
        if ($quantReportPath.StartsWith($containerPrefix)) {
            $relativePath = $quantReportPath.Substring($containerPrefix.Length).Replace("/", [IO.Path]::DirectorySeparatorChar)
            $quantReportHostPath = Join-Path $projectRoot "freqtrade/$relativePath"
        }
        if (-not (Test-Path -LiteralPath $quantReportHostPath)) {
            $errors.Add("Live quant gate report does not exist.")
        }
        else {
            try { $quantReport = Get-Content -LiteralPath $quantReportHostPath -Raw | ConvertFrom-Json }
            catch { $errors.Add("Live quant gate report is not valid JSON."); $quantReport = $null }
            if ($null -ne $quantReport -and $quantReport.passes -ne $true) {
                $errors.Add("Live quant gate report does not pass.")
            }
            if ($null -ne $approval) {
                $digest = (Get-FileHash -LiteralPath $quantReportHostPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($digest -ne [string]$approval.quant_report_sha256.ToLowerInvariant()) {
                    $errors.Add("Live quant gate report SHA-256 does not match the approval record.")
                }
            }
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
    clock_drift_seconds = $clockDriftSeconds
} | ConvertTo-Json
