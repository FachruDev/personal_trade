# Trading Bot

Binance Spot bot for BTC/USDT and ETH/USDT. The default runtime is the conservative paper profile: one position and 25% of the virtual wallet. Futures and leverage are excluded.

## Start locally

1. Copy `.env.example` to `.env` and replace every placeholder password/token.
   `FREQTRADE_API_PASSWORD` must contain ASCII characters only.
2. Keep `FREQTRADE_PROFILE_CONFIG=/freqtrade/user_data/config/profiles/paper-conservative.json`, `FREQTRADE_STRATEGY=LimitedRiskRegimeRiskStrategy`, and `TRADING_ENVIRONMENT=paper` in `.env`.
3. Start Docker Desktop, then run `docker compose --env-file .env.example up --build`.
4. Check `http://localhost:8000/health` and open the operator dashboard at `http://localhost:3000`.

Freqtrade sends internal lifecycle webhooks to the API. These events are stored
in PostgreSQL and are available through `GET /v1/decisions`; the local dashboard
uses that endpoint for its decision timeline.

## Backtest

Download historical candles:

```powershell
docker compose --env-file .env.example run --rm freqtrade freqtrade download-data --config /freqtrade/user_data/config.json --pairs BTC/USDT ETH/USDT --timeframes 1h 4h --days 180
```

Run the backtest:

```powershell
docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy RegimeRiskStrategy --timeframe 1h
```

Evaluate a frozen candidate only after producing three separate artifacts. The command exits with status `1` when any release metric fails, which is the expected outcome for rejected candidates.

```powershell
.\scripts\evaluate-backtest-gates.ps1 -Label candidate-name `
  -Development freqtrade/backtest_results/candidate_development.zip `
  -Validation freqtrade/backtest_results/candidate_validation.zip `
  -OutOfSample freqtrade/backtest_results/candidate_out_of_sample.zip
```

The saved report is ignored by Git under `docs/quant-reports/`; record the conclusion and essential metrics in [quant-validation.md](docs/quant-validation.md).

Candidates that pass the three-period gate must then pass the fixed rolling-forward protocol. It uses five pre-registered six-month windows, applies no tuning between windows, and fails if any fold misses the same trade-count, profit-factor, expectancy, or drawdown gate.

```powershell
.\scripts\run-walk-forward-validation.ps1 `
  -Label candidate-name `
  -Strategy CandidateStrategy
```

The rolling-forward report is also saved under `docs/quant-reports/`. It is research evidence only and does not change the active paper strategy.

## Release profiles

Validate the active paper profile before starting it:

```powershell
.\scripts\preflight-release.ps1 -Mode paper
```

The live template is deliberately not activated. Follow [the go-live checklist](docs/go-live-checklist.md) before creating the ignored `live.local.json` profile and using a restricted Binance API key. Compose also refuses a live Freqtrade startup without an ignored, dated `live-release-approval.local.json` record and its configured `LIVE_RELEASE_APPROVAL_FILE`.

The ordered procedure for the approved limited-live release is in [limited-live-runbook.md](docs/limited-live-runbook.md). It includes the non-interactive local stop/resume commands and does not place the control token in terminal history.

## Shadow market context

`GET /v1/context/global` returns the most recently stored CoinGecko global-market snapshot. By default the API refreshes this public snapshot every 15 minutes through `GLOBAL_SHADOW_REFRESH_SECONDS=900`; set the value to `0` to disable the scheduler. Refreshing it manually still requires the local control token through `POST /v1/context/global/refresh`.

Provider or malformed-response failures are recorded as audit events and do not affect API health, the bot lifecycle, or order execution. The snapshot is audit-only and does not alter trading decisions.

`GET /v1/context/orderbook` exposes public Binance top-of-book telemetry for BTCUSDT and ETHUSDT. It records mid-price, top-ten-level notional imbalance, and spread every five minutes by default (`ORDERBOOK_SHADOW_REFRESH_SECONDS=300`). This is a separate research series for testing an independent microstructure hypothesis; it uses no exchange credentials and cannot affect orders.

`GET /v1/context/orderbook/coverage` reports how much history is available. The default research gate is 8,064 snapshots (four weeks at five-minute cadence) with at least 95% cadence coverage; until then the series is collecting data and is not evidence for a strategy change. It also reports the remaining snapshots, a cadence-based estimated-ready timestamp, and the outage threshold that would begin a new evidence segment. The estimate is operational planning only, never a promotion signal.

The schedulers preserve the previous collection cadence after an API restart, and order-book coverage counts distinct five-minute buckets rather than restart duplicates. A one-hour-or-longer order-book outage starts a new collection segment for research readiness while preserving older raw snapshots for audit.

After that gate, `GET /v1/research/orderbook/forward-returns?pair=BTCUSDT&horizon_minutes=60` evaluates only the pre-declared 60-minute or 240-minute horizons and the three pre-declared imbalance buckets: bid-heavy, neutral, and ask-heavy. It is a research report only and never reaches Freqtrade.

`GET /v1/research/orderbook/report` is the cockpit-oriented read-only version of the same protocol. It exposes only BTCUSDT/ETHUSDT and the pre-declared 60/240-minute horizons; before the coverage gate it returns the collection status and no evaluation.

When the quant strategy identifies an entry candidate, it records the current context-fusion recommendation in that candidate's audit event. This is best-effort shadow telemetry only: unavailable context, its recommendation, and its risk multiplier never block or change an order.

`GET /v1/context/macro` exposes the most recent FRED macro snapshot. With `FRED_API_KEY` configured, the API refreshes it automatically every `MACRO_SHADOW_REFRESH_SECONDS` (six hours by default); set that value to `0` to disable automatic collection. FRED issues a 32-character lowercase alphanumeric API key. Put it only in `.env`, then run `docker compose up -d --force-recreate api` so the local API receives the new value. The local, token-protected `POST /v1/context/macro/refresh` endpoint remains available for a manual refresh. Macro context is audit-only.

## Shadow news pipeline

With `NEWS_API_KEY` configured, the NewsAPI headline collector refreshes automatically every `NEWS_SHADOW_REFRESH_SECONDS` (one hour by default); set that value to `0` to disable automatic collection. The local, token-protected `POST /v1/news/headlines/refresh` endpoint remains available for a manual refresh. It deduplicates crypto headlines, stores them in PostgreSQL, and exposes them through `GET /v1/news/headlines`. The dashboard renders the collected headlines as research context only; they do not change entries, exits, position size, or risk limits.

## Binance market status

`GET /v1/market/binance/status` checks the public Binance endpoint for BTCUSDT and ETHUSDT, plus Binance server time, and caches the result for one minute. It uses no exchange credential and is shown on the operator dashboard so pair availability and local clock drift are visible. Drift above two seconds is shown as a warning; synchronize the host clock before a release.

## Paper-run continuity

`GET /v1/paper-run` reports persisted Freqtrade-health heartbeats for the paper environment. The API records a heartbeat every 15 minutes by default and starts a new continuity segment after a 30-minute gap. Each heartbeat includes the selected strategy, profile, `PAPER_RUN_REVISION`, and SHA-256 digest of the read-only mounted strategy source. Any identity change starts a new segment. The release dashboard requires a complete 56-day segment; a restart alone does not reset the record, while an actual monitoring gap remains visible as an interruption. It reports evidence progress toward 56 days separately from heartbeat cadence coverage; a 100% cadence on the first heartbeat does not mean the eight-week evidence requirement is complete.

## Data retention

The application database is separate from Freqtrade's trade database. Run `./scripts/run-retention.ps1 -Preview` first to count eligible records without deleting anything. Run `./scripts/run-retention.ps1` only after the preview is reviewed to remove expired audit, context, news, and AI-shadow records. Defaults are configured through the retention variables in `.env.example`; the deletion command records its own completion event.
