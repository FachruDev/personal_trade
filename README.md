# Trading Bot MVP

Binance Spot dry-run bot for BTC/USDT and ETH/USDT. The strategy uses a 4H market-regime filter and 1H quant entry rules. Futures and live execution are intentionally excluded.

## Start locally

1. Copy `.env.example` to `.env` and replace every placeholder password/token.
   `FREQTRADE_API_PASSWORD` must contain ASCII characters only.
2. Start Docker Desktop, then run `docker compose --env-file .env.example up --build`.
3. Check `http://localhost:8000/health`.

## Backtest

Download historical candles:

```powershell
docker compose --env-file .env.example run --rm freqtrade freqtrade download-data --config /freqtrade/user_data/config.json --pairs BTC/USDT ETH/USDT --timeframes 1h 4h --days 180
```

Run the backtest:

```powershell
docker compose --env-file .env.example run --rm freqtrade freqtrade backtesting --config /freqtrade/user_data/config.json --strategy RegimeRiskStrategy --timeframe 1h
```

The untouched Next.js project now lives in `apps/web` and is intentionally not part of this MVP runtime.
