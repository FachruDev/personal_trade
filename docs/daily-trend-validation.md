# Daily Trend Validation

Status: **research candidate**. It is not the active paper strategy and is not approved for live trading.
Switching the paper bot to it starts a new paper-run continuity segment (strategy identity changes), so
that decision is deliberately left to the operator.

## Why this exists

All twelve 1H experiments in [quant-validation.md](quant-validation.md) were rejected. Measured on the
local data, a typical 1H move is 0.32% (BTC) and 0.44% (ETH), so a 0.20% round trip plus slippage consumes
57–77% of it. On daily candles the same cost is 10–15% of a typical move. This candidate therefore moves
to the daily timeframe and targets **drawdown control**, not prediction.

## Pre-registered design

Fixed before looking at results; the only fitted-looking choice is the SMA family, which was suggested by
earlier BTC/ETH grids (see the caveats).

- Pairs: BTC/USDT and ETH/USDT, equal capital budget each. Spot, long-or-cash, no leverage.
- Trend score: share of {SMA50, SMA100, SMA150} that sit below the last daily close.
- Volatility scale: `min(1, 40% / 20-day annualised realised volatility)`.
- Target exposure = trend score × volatility scale. Exit completely when the score is zero.
- Dead-band: resize only when the target moves by more than 10 percentage points.
- Execution: signal on a closed daily candle, trade at the next daily open.
- Disaster stop: −30% from entry (research model has none; it only fired once in the engine backtest).

Core rules live in `packages/trading_core/src/trading_core/trend.py` (pure Python, broker-agnostic);
the Freqtrade adapter is `freqtrade/strategies/DailyTrendVolStrategy.py`.

## Evidence

Research model (daily pandas, 0.10% fee + 0.05% slippage per side, open-to-open), 2018-03 onward,
BTC+ETH 50/50 buy-and-hold for comparison:

| | Buy & hold | Trend ensemble |
| --- | ---: | ---: |
| Sharpe | 0.67 | 1.26 |
| Max drawdown (daily mark-to-market) | −83% | −37% |
| Average market exposure | 100% | 36% |
| Sharpe difference, paired block bootstrap 5/50/95% | | +0.15 / +0.59 / +1.03 |

On the engine's window (from 2018-04-01, 0.10% per side, no slippage) the research model gives strategy
CAGR 37.8% and drawdown −36%, against buy-and-hold CAGR 33.3% and drawdown −81%.

Freqtrade engine (`scripts/run_daily_trend_backtest.ps1`, fee 0.1%, no slippage, wallet 1,000 USDT; each
period restarts the wallet). The result depends on how much of the wallet is deployed
(`tradable_balance_ratio`), so both bases are shown. Percentages are of the whole wallet.

| Period | Full deployment (0.99): CAGR / drawdown | Paper profile (0.25): CAGR / drawdown | Market change | Trades |
| --- | ---: | ---: | ---: | ---: |
| 2018-04 → 2026-10 (full) | 33.7% / 35.0% | 9.0% / 13.9% | +851% | 118 |
| 2018-04 → 2021-12 | 53.5% / 20.8% | 13.4% / 10.6% | +748% | 50 |
| 2022-01 → 2023-12 | 12.1% / 24.3% | 3.7% / 6.8% | −22% | 33 |
| 2024-01 → 2026-10 | 25.1% / 23.4% | 6.7% / 6.8% | +49% | 37 |

The paper profile deploys only a quarter of the wallet, matching the existing conservative paper cap, so
its absolute returns and drawdowns are much smaller. Judge the strategy by the ratio of return to drawdown,
not by the paper-profile CAGR.

Engine (full deployment) and research model agree: 33.7% against 37.8% CAGR on the same window and a 0.10% cost. The
engine is the lower, more realistic number.

Robustness (research model): Sharpe stays between 1.1 and 1.3 across volatility targets of 30–50%, five
SMA sets, and costs up to 0.30% per side (CAGR 34.7%, Sharpe 1.23).

## What this does and does not show

- **The edge is drawdown, not extra return.** From 2018-04-01 the 50/50 buy-and-hold CAGR is 33.3%, only
  slightly below the strategy. Starting one month earlier (2018-03-01) makes buy-and-hold look much worse
  (24%) because ETH halved in March 2018; return comparisons are start-date sensitive, the drawdown
  comparison (−37% against −81%) is not.
- Gains are regime dependent. The strategy lags in strong bull markets (2024-onward: 25% against +49%
  market) and earns most of its advantage in crashes (2018, 2022).
- About a fifth of the engine's total profit (2,466 of 10,876 USDT) comes from the two positions that were
  still open and force-exited at the end of the test.
- Per-trade statistics look odd and are not a defect: win rate is 14%, average per-trade return is
  negative, and a trade averages 7 orders. Stakes grow with compounding, so many small early losers sit
  beside a few large long winners, and resizing adds orders to long-running positions.
- Freqtrade's `Sharpe (closed trades)` of 0.17 is a per-trade statistic and is not comparable with the
  daily-equity Sharpe above.

## Known weaknesses

- Only two assets and roughly two bear markets (2018, 2022). Selection of BTC and ETH is itself
  survivorship-biased.
- The SMA family and the volatility-target idea were influenced by earlier grids on 2019-onward data, so
  those years are not fully out-of-sample. 2018 was the first genuinely unseen bear market.
- The backtest assumes fills at the daily open. Live limit orders, partial fills, exchange downtime and
  minimum-notional effects are untested.
- Realistic planning drawdown is 35–40% of the invested balance, not the 5% gate designed for the 1H model.

## Proposed gates (not yet adopted — operator decision)

The 1H gates (≤5% drawdown, ≥30 trades per fold) do not fit a slow daily strategy. Proposed replacement for
promoting this candidate to a paper run:

1. Maximum drawdown no worse than half of the 50/50 buy-and-hold drawdown in the same window.
2. Sharpe at least equal to buy-and-hold on the full window, and positive CAGR in every regime segment
   above except a strong bull market.
3. Results survive 0.30% per side cost.
4. No unresolved operational faults in 56 days of continuous paper trading, and paper drawdown inside the
   35–40% planning band.

## Reproduce

```powershell
.\scripts\run_daily_trend_backtest.ps1            # Freqtrade engine, all reporting periods
```

Research scripts (`research/`, see [research/README.md](../research/README.md)) reproduce every research
figure here. Unit tests: `python -m pytest tests/unit` and the Freqtrade container test command in the
research README.

## Running it in paper (when you decide to)

1. Check the profile. The paper preflight allows one open trade by default; this strategy trades BTC and ETH
   together, so pass the explicit paper-only override (live keeps its one-trade limit):

   ```powershell
   .\scripts\preflight-release.ps1 -Mode paper -ProfilePath freqtrade\config\profiles\paper-daily-trend.json -PaperMaxOpenTrades 2
   ```

2. Set these in `.env` so the paper-run heartbeat records the right identity (otherwise evidence is
   mislabelled):

   ```text
   FREQTRADE_PROFILE_CONFIG=/freqtrade/user_data/config/profiles/paper-daily-trend.json
   FREQTRADE_STRATEGY=DailyTrendVolStrategy
   PAPER_STRATEGY_SOURCE_FILE=/freqtrade/user_data/strategies/DailyTrendVolStrategy.py
   PAPER_RUN_REVISION=daily-trend-v1
   ```

3. Rebuild and recreate: `docker compose up -d --build`. The dashboard (port 3000) shows the active strategy,
   target exposure per pair, and paper-run status; Freqtrade's own UI on port 8080 shows individual trades.

Changing the strategy, its source, or the revision label starts a new paper-run segment by design.
Keep Docker running without gaps: a gap longer than 30 minutes interrupts the evidence segment.
