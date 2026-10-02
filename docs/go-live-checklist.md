# Go-live checklist

This checklist is intentionally a release gate, not a promise that the current strategy is ready. The current strategy remains disqualified by the results in `quant-validation.md`.

## Quant gate

- [ ] A frozen strategy revision has positive expectancy and profit factor of at least 1.15 in both validation and out-of-sample periods.
- [ ] The candidate has at least 30 closed trades in each decision-relevant test set, without a single-pair dependency.
- [ ] Maximum drawdown remains at or below 5% in the forward-test account.
- [ ] Look-ahead and recursive analysis pass for the frozen strategy.
- [ ] Fees, spread, and realistic slippage assumptions are included in the final evaluation.
- [ ] The frozen candidate has been evaluated with `scripts/evaluate-backtest-gates.ps1`; its saved gate report passes for development, validation, and out-of-sample artifacts.

## Paper-release gate

- [ ] `scripts/preflight-release.ps1 -Mode paper` passes.
- [ ] The bot has completed at least eight uninterrupted weeks of dry-run with the frozen strategy and fixed profile.
- [ ] Audit records trace a sample entry, rejected entry, protection event, partial exit, and final exit.
- [ ] Pause/resume, restart, API outage, PostgreSQL outage, Redis outage, and Binance connectivity failure were exercised and returned the bot to a safe state. Pause/resume, Freqtrade restart, and API/PostgreSQL/Redis outages passed in the paper environment on 2 October 2026; provider and Binance-connectivity tests remain. See [operational validation](operational-validation.md).

## Limited-live gate

- [ ] The owner explicitly approves a dated release record after reviewing the quant and paper-release evidence.
- [ ] A dedicated Binance API key has Spot Trading only, has no withdrawal permission, and has an IP allowlist.
- [ ] `freqtrade/config/profiles/live.local.json` is created from `live.template.json`; it remains ignored by Git and passes `scripts/preflight-release.ps1 -Mode live`. The preflight requires `TRADING_ENVIRONMENT=live` plus non-placeholder Binance and local-control credentials in `.env`.
- [ ] An ignored `live-release-approval.local.json` is created from its template with the dated owner approval, immutable strategy revision, final paper-run timestamp, and SHA-256 of the passed frozen quant report. `LIVE_RELEASE_APPROVAL_FILE` points to it. Compose validates this record again at live container startup.
- [ ] `TRADING_ENVIRONMENT=live`, `FREQTRADE_PROFILE_CONFIG=/freqtrade/user_data/config/profiles/live.local.json`, and `FREQTRADE_STRATEGY=LimitedRiskRegimeRiskStrategy` are set only in the deployment environment.
- [ ] Emergency stop and operator credentials have been verified locally before starting the bot.
- [ ] The initial live release uses one position and at most 10% of the dedicated trading account.

Passing configuration preflight does not satisfy the quant or paper-release gate. It only proves that a selected configuration obeys the limited-release risk envelope.
