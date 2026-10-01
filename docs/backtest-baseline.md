# Quant Baseline Backtest

Run date: 1 October 2026.  
Data: Binance Spot, BTC/USDT and ETH/USDT, 1H entries with a 4H informative trend filter.  
Period: 13 April 2026 through 1 October 2026 after indicator warm-up.

| Metric | Result |
| --- | ---: |
| Starting balance | 1,000 USDT |
| Final balance | 940.01 USDT |
| Total profit | -6.00% |
| Trades | 30 |
| Win rate | 20.0% |
| Profit factor | 0.51 |
| Maximum drawdown | 9.26% |
| Stop-loss exits | 22 |
| Take-profit-2 exits | 4 |

## Decision

This baseline is **not approved** for an extended dry-run observation period. The next strategy phase is analysis and validation: inspect the ETH losses, check for look-ahead bias, and revise entry or regime thresholds only from measured results. AI, macro, and news data remain disabled until the quant-only baseline has acceptable risk-adjusted performance.

## Per-pair diagnostic

The combined loss is concentrated in ETH/USDT, rather than being shared evenly by both assets.

| Pair | Trades | Total profit | Win rate | Profit factor | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT | 14 | -0.49% | 35.7% | 0.91 | 4.01% |
| ETH/USDT | 16 | -6.01% | 6.2% | 0.18 | 6.81% |

ETH/USDT produced 13 stop-loss exits from 16 trades. The next controlled experiment should therefore test the regime and entry conditions separately on ETH before changing position size, take-profit, or any global risk limit. BTC also remains below an acceptable threshold, so it is retained only as a benchmark and is not enabled for a prolonged dry-run.

## Validation

Freqtrade look-ahead analysis ran against the same timerange and found no biased entry signals, exit signals, or indicators. The negative result is therefore a strategy-quality issue, not evidence of future-data leakage.
