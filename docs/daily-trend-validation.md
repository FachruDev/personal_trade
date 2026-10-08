# Daily Trend Validation

Status: **research candidate, running in paper only**. It is not approved for live trading. Changing the
strategy, its source, or the revision label starts a new paper-run segment by design.

## Why this exists

All twelve 1H experiments in [quant-validation.md](quant-validation.md) were rejected. Measured on the
local data, a typical 1H move is 0.32% (BTC) and 0.44% (ETH), so a 0.20% round trip plus slippage consumes
57–77% of it. On daily candles the same cost is 10–15% of a typical move. This candidate therefore moves
to the daily timeframe and targets **drawdown control**, not prediction.

## Design

- Pairs: BTC/USDT and ETH/USDT, equal capital budget each. Spot, long-or-cash, no leverage.
- Trend score: share of {SMA50, SMA100, SMA150} that sit below the last daily close.
- Volatility scale: `min(1, 30% / 20-day annualised realised volatility)`.
- Target exposure = trend score × volatility scale. Exit completely when the score is zero.
- Dead-band: resize only when the target moves by more than 10 percentage points.
- Execution: signal on a closed daily candle, trade at the next daily open.
- Disaster stop: −30% from a position's average entry.
- Circuit breaker: Freqtrade `MaxDrawdown` protection pauses new entries for 30 days after a drawdown of
  30% of the capital this strategy deploys (the threshold is scaled by `tradable_balance_ratio`, because
  Freqtrade measures it against the whole account, and it sees closed trades only).

The structure (SMA ensemble plus volatility targeting) was fixed before looking at results. The volatility
target was first 40%. It was lowered to 30% because the operator's stated crypto drawdown tolerance is
30–40% and 40% left almost no margin; the choice follows the risk budget, not a search for return.

Core rules live in `packages/trading_core/src/trading_core/trend.py` (pure Python, broker-agnostic);
the Freqtrade adapter is `freqtrade/strategies/DailyTrendVolStrategy.py`.

## Risk limits this is meant to respect

| Capital | Operator tolerance | This strategy (engine, mark-to-market) |
| --- | --- | --- |
| Crypto sleeve, fully deployed | 30–40% | 27.3% worst drawdown, 2018-04 to 2026-10 |
| Whole account, 25% deployed (paper profile) | 10–20% (active trading) | 7.6% worst drawdown |

The historical worst case is a floor on future risk, not a ceiling. The 27% result leaves 3–13 points of
margin to the stated tolerance.

## Evidence

Research model (daily pandas, 0.10% fee plus 0.05% slippage per side, open-to-open), 30% target, from
2018-03 against 50/50 BTC+ETH buy-and-hold:

| | Buy & hold | Trend ensemble |
| --- | ---: | ---: |
| CAGR | 24% | 28% |
| Sharpe | 0.67 | 1.24 |
| Max drawdown (daily mark-to-market) | −83% | −28% |

Return comparisons depend on the start date (from 2018-04-01 buy-and-hold CAGR is 33.3%, because ETH
halved in March 2018), whereas the drawdown comparison (−28% against −81%) does not. The supported claim is
the drawdown reduction. A paired block bootstrap of the Sharpe difference on the original 40% design gave
+0.15 / +0.59 / +1.03 at 5/50/95%.

Freqtrade engine (`scripts/run_daily_trend_backtest.ps1`, fee 0.1%, no slippage, 1,000 USDT; each period
restarts the wallet; drawdown is mark-to-market and rebuilt by `research/11_engine_mark_to_market.py`).
Percentages are of the whole wallet, so they depend on how much is deployed:

| Period | Full deployment (0.99): CAGR / drawdown / Sharpe | Paper profile (0.25): CAGR / drawdown / Sharpe |
| --- | ---: | ---: |
| 2018-04 → 2026-10 | 29.4% / −27.3% / 1.30 | 7.4% / −7.6% / 1.34 |
| 2018-04 → 2021-12 | 45.2% / −18.9% / 1.71 | 11.0% / −5.1% / 1.80 |
| 2022-01 → 2023-12 | 12.7% / −18.9% / 0.71 | 2.5% / −5.5% / 0.55 |
| 2024-01 → 2026-10 | 21.0% / −21.9% / 1.05 | 3.8% / −6.5% / 0.78 |

Engine and research model agree on the same window and cost (2018-04, 0.10%): CAGR 29.4% against 29.2%,
drawdown −27.3% against −28.1%, Sharpe 1.30 against 1.30. The paper profile deploys a quarter of the
wallet, matching the existing conservative cap, so its absolute figures are smaller; judge the strategy
by return relative to drawdown.

Robustness (research model): Sharpe stays between 1.1 and 1.3 across volatility targets of 30–50%, five SMA
sets, and costs up to 0.30% per side.

The circuit breaker is insurance, not a measured benefit: it never fired at full deployment and changed
the paper-profile result by about 0.1 point of CAGR.

## Correction record

An earlier version of this document reported engine results of 33.7% CAGR and −35% drawdown. Those were
distorted by two defects in the strategy that the model comparison exposed:

1. Partial-exit requests were written in market-value units, but Freqtrade reads a negative stake as a
   share of the trade's cost basis. On a profitable position the request exceeded the whole position and
   was silently ignored, so ETH was never trimmed during the 2021 rally and reached 53% of the account when
   the target was 17%.
2. The per-pair budget used `get_total_stake_amount`, which values open trades at cost, so budgets
   lagged while positions were in profit.

Both are fixed and covered by tests (`freqtrade/tests/test_daily_trend_strategy.py`). Numbers above are
from the corrected strategy; ignore any figure from before that fix.

## What this does and does not show

- **The edge is drawdown, not extra return.** The strategy lags in strong bull markets and earns its
  advantage in crashes (2018, 2022).
- Per-trade statistics look odd and are not a defect: win rate is low, the average per-trade return is
  negative, and a trade averages several orders. Stakes grow with compounding, and resizing adds orders to
  long-running positions.
- Freqtrade's `Sharpe (closed trades)` is a per-trade statistic and is not comparable with the daily-equity
  Sharpe above.

## Known weaknesses

- Only two assets and roughly two bear markets (2018, 2022). Selection of BTC and ETH is itself
  survivorship-biased.
- The SMA family was influenced by earlier grids on 2019-onward data, so those years are not fully
  out-of-sample. 2018 was the first genuinely unseen bear market.
- The backtest assumes fills at the daily open. Live limit orders, partial fills, exchange downtime and
  minimum-notional effects are untested; paper trading tests the plumbing, not the edge (the strategy
  makes only a handful of trades per pair per year).
- The circuit breaker sees closed trades only; open losses are limited by volatility targeting and the
  −30% disaster stop.

## Proposed gates (not yet adopted — operator decision)

The 1H gates (≤5% drawdown, ≥30 trades per fold) do not fit a slow daily strategy. Proposed replacement for
promoting this candidate beyond paper:

1. Maximum drawdown no worse than half of the 50/50 buy-and-hold drawdown in the same window (met:
   −27% against −81%).
2. Sharpe at least equal to buy-and-hold on the full window, and positive CAGR in every regime segment
   above except a strong bull market (met).
3. Results survive 0.30% per side cost (met in the research model).
4. No unresolved operational faults in 56 days of continuous paper trading, and paper drawdown inside the
   operator's tolerance (30% of the deployed capital).

## Reproduce

```powershell
.\scripts\run_daily_trend_backtest.ps1                     # paper profile, breaker on
.\scripts\run_daily_trend_backtest.ps1 -Deployment full    # research profile, 99% deployed
.\scripts\run_daily_trend_backtest.ps1 -NoProtections      # without the circuit breaker
```

Research scripts (`research/`, see [research/README.md](../research/README.md)) reproduce every research
figure. Unit tests: `python -m pytest tests/unit` and the Freqtrade container test command in the research
README.

## Running it in paper

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
   PAPER_RUN_REVISION=daily-trend-v2
   ```

3. Rebuild and recreate: `docker compose --env-file .env.example up -d --build`. The dashboard (port 3000)
   shows the active strategy, target exposure per pair, and paper-run status; Freqtrade's own UI on port 8080
   shows individual trades.

Keep Docker running without gaps: a gap longer than 30 minutes interrupts the evidence segment. For a
24/7 host see [vps-migration-guide.md](vps-migration-guide.md).
