# Research scripts

Reproducible pandas research behind [docs/daily-trend-validation.md](../docs/daily-trend-validation.md)
and the experiments added to [docs/quant-validation.md](../docs/quant-validation.md). Nothing here
touches the trading bot or any exchange account; it only reads public data.

## Setup

```powershell
cd research
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Run every script from this folder. `data/` is ignored by Git.

## Data

| Data | How to get it |
| --- | --- |
| 20 daily Binance spot series since 2017 | `python fetch_crypto_daily.py` (public klines, no key) |
| Daily G10 FX rates against USD, 1999 onward | `python fetch_fx.py` (Frankfurter / ECB reference rates) |
| Short-term interest rates | Download `IR3TIB01xxM156N` CSVs from FRED into `data/rates/` for `US`, `EZ`, `GB`, `JP`, `CH`, `AU`, `CA` |
| 1H BTC/ETH candles | Already in `../freqtrade/data/binance` after the existing backtest download |

Each script drops the incomplete current-day candle. The coin universe in `fetch_crypto_daily.py` is a list
of coins that exist today (EOS is the only delisted one), so any cross-sectional result is survivorship
biased and should be read as an upper bound.

## Scripts

| Script | Question |
| --- | --- |
| `01_btc_eth_trend_grid.py` | Does an SMA trend filter beat buy-and-hold on BTC and ETH, and is it stable across lookbacks? |
| `02_multi_asset_momentum.py` | Equal-weight trend and cross-sectional momentum over 20 coins, by period |
| `03_significance_tests.py` | Paired block bootstrap of the Sharpe difference; deflated Sharpe (**note**: deflated Sharpe against zero is meaningless when the benchmark already has Sharpe ≈ 1) |
| `04_one_hour_signal_diagnostic.py` | Gross edge of the existing 1H entry rule before costs |
| `05_move_size_vs_cost.py` | Typical move size against round-trip cost on 1H, 4H and 1D |
| `06_daily_trend_ensemble.py` | The pre-registered daily candidate, with every sensitivity reported |
| `07_engine_comparison_and_cost_stress.py` | Same window as the Freqtrade backtest, and cost stress up to 0.30% per side |
| `11_engine_mark_to_market.py` | Rebuild daily mark-to-market equity from a Freqtrade backtest result zip, so engine and research drawdowns are comparable |
| `08_fx_trend.py` | G10 FX time-series momentum against USD |
| `09_fx_carry.py`, `10_fx_carry_decomposition.py` | G10-subset carry, and its split into carry and spot components |

`lib.py` holds the shared execution model: signal at the close, trade at the next open, hold open to
open, 0.15% cost per side on traded notional.

## Test commands

```powershell
python -m pytest tests/unit      # run from the repository root; pure core logic
docker compose --env-file .env.example run --rm --no-deps -e PYTHONPATH=/freqtrade/user_data/strategies freqtrade python -m unittest discover -s /freqtrade/user_data/tests
```

After changing anything under `packages/trading_core`, rebuild first:
`docker compose --env-file .env.example build freqtrade` (the package is copied into the image).

## Findings in one paragraph

Daily BTC/ETH trend filtering with volatility targeting roughly halves drawdown at similar return. G10 FX
trend and a six-currency carry basket showed no durable edge. Only six currencies were available for
carry (NZD, SEK and NOK were missing), the rates are interbank rather than tradable broker swaps, and the
test is spot-only, so the FX conclusion is "not shown", not "proven absent".
