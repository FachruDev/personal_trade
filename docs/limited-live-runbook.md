# Limited-live Runbook

This runbook is for the first **Binance Spot limited-live** release only. It does not authorize release by itself. Complete every gate in [go-live-checklist.md](go-live-checklist.md) before changing the running paper environment.

## Before changing configuration

1. Freeze the strategy revision that passed the quant gate and preserve its backtest artifacts plus release-gate report.
2. Complete the required eight-week fixed-profile dry-run and record its evidence.
3. Use a dedicated Binance API key with Spot Trading permission only, withdrawal disabled, and an IP allowlist for the deployment host.
4. Keep BTC/USDT and ETH/USDT as the only pairs. Do not enable futures, margin, leverage, or new pairs.
5. Create `freqtrade/config/profiles/live.local.json` from `live.template.json`. Keep it ignored by Git.

## Prepare the deployment environment

Set these deployment-only values in `.env`:

```text
TRADING_ENVIRONMENT=live
FREQTRADE_PROFILE_CONFIG=/freqtrade/user_data/config/profiles/live.local.json
FREQTRADE_STRATEGY=LimitedRiskRegimeRiskStrategy
```

Fill the dedicated Binance key and secret, then verify the local control token, Freqtrade API password, and JWT secret are not placeholders. Do not copy these values into documentation, terminal history, or source control.

Run the preflight. It must pass before the service is started:

```powershell
.\scripts\preflight-release.ps1 -Mode live
```

## Start and verify

Start the stack with the approved production `.env`, then verify the dashboard reports `live`, Binance pair status is `TRADING`, Freqtrade is connected, and the kill-switch is ready. The initial profile must allow only one open position and at most 10% of the dedicated account.

Observe the first entry, fill, protection event, and exit in the audit timeline. Stop the bot immediately if the execution result diverges from the frozen strategy or the risk envelope.

## Emergency control

Preview the local commands without taking action:

```powershell
.\scripts\control-bot.ps1 -Action Stop -WhatIf
.\scripts\control-bot.ps1 -Action Resume -WhatIf
```

To stop new entries and request a Freqtrade stop, run:

```powershell
.\scripts\control-bot.ps1 -Action Stop
```

After reviewing the incident and confirming the operating environment is healthy, resume with:

```powershell
.\scripts\control-bot.ps1 -Action Resume
```

Both actions use the control token only inside the API container and write an audit event.
