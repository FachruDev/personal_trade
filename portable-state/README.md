# Portable server state

This directory is the optional, Git-trackable migration package for data that
must survive a server move. It intentionally contains no `.env` file, exchange
keys, API keys, passwords, or JWT secrets.

Run the following on the source host while PostgreSQL is healthy:

```powershell
.\scripts\export-portable-state.ps1
```

It creates a timestamped PostgreSQL custom dump and `manifest.json`. The dump
contains the application audit trail, paper-run evidence, order-book snapshots,
macro/global context, news headlines, and AI shadow assessments. It also copies
any Freqtrade SQLite trade database found below `freqtrade/`.

Historical candle files are optional because the live dry-run bot can fetch new
candles from Binance. Include them only when reproducible local backtests on the
VPS are required:

```powershell
.\scripts\export-portable-state.ps1 -IncludeHistoricalData
```

Commit the resulting package only to a private repository. A private repository
reduces exposure but is not a secret manager: never add `.env`, API keys,
passwords, or production credentials.

On the destination VPS, clone the repository, create a new local `.env`, place
the portable-state package in this directory, and restore before starting API,
web, or Freqtrade:

```powershell
.\scripts\import-portable-state.ps1 -Source .\portable-state -Force
docker compose up -d
```

The restore intentionally refuses to overwrite a running API, web dashboard, or
Freqtrade process. Only one bot instance may run at a time. A migration outage
can reset continuity evidence; verify the paper-run segment after the VPS starts.
