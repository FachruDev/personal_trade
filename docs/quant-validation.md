# Quant Validation Register

## Dataset dan aturan evaluasi

- Market: Binance Spot, BTC/USDT dan ETH/USDT.
- Timeframe: entry 1H, informative regime 4H.
- Data tersedia: 3 October 2023 sampai 2 October 2026.
- Fee tetap memakai konfigurasi backtest Freqtrade sebesar 0.1% sebagai baseline konservatif.
- Parameter belum dituning pada hasil di bawah ini. Semua hasil menggunakan `RegimeRiskStrategy` yang sama.

## Baseline multi-periode

| Period | Range | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | 13 Oct 2023 – 1 Oct 2025 | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| Validation | 1 Oct 2025 – 1 Apr 2026 | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| Out-of-sample | 1 Apr 2026 – 2 Oct 2026 | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |

Validation has only four trades, so it is not statistically useful as a pass signal.

## Per-pair diagnostic

| Period | Pair | Trades | Return | Profit factor | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: |
| Development | BTC/USDT | 100 | -23.27% | 0.41 | 23.61% |
| Development | ETH/USDT | 70 | +0.41% | 1.02 | 6.12% |
| Out-of-sample | BTC/USDT | 17 | +1.92% | 1.36 | 2.77% |
| Out-of-sample | ETH/USDT | 25 | -4.90% | 0.53 | 7.91% |

## Decision

The strategy is rejected as a live candidate. It is not robust across market periods: BTC is negative in development but positive in out-of-sample, while ETH reverses from near-flat development performance to a material out-of-sample loss. Removing one pair based only on the latest period would overfit the result.

## Controlled experiment protocol

1. Change exactly one decision variable per experiment, starting with the 4H regime strength filter (ADX threshold).
2. Run the same development, validation, and out-of-sample ranges for both pairs and the combined portfolio.
3. Record the strategy revision, parameter value, trade count, return, profit factor, expectancy, and drawdown in this file.
4. Reject a candidate when development, validation, or out-of-sample performance is negative or when validation has too few trades to support the conclusion.
5. Run look-ahead analysis for each candidate that survives the metric gate.

The next experiment is not yet selected as a winner. It will compare a small, pre-declared ADX threshold range against this baseline before changing stop-loss, take-profit, position sizing, or adding external data.

## Experiment 001 — 4H ADX strength threshold

Only the 4H ADX minimum was changed. The baseline is 20; the candidates are 25 and 30. All other inputs and evaluation ranges are unchanged.

| ADX minimum | Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 20 | Development | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| 20 | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 20 | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |
| 25 | Development | 112 | -16.71% | 0.58 | -1.49 USDT | 16.98% |
| 25 | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 25 | Out-of-sample | 30 | +0.07% | 1.01 | +0.02 USDT | 6.05% |
| 30 | Development | 87 | -12.62% | 0.61 | -1.45 USDT | 14.67% |
| 30 | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 30 | Out-of-sample | 20 | +0.13% | 1.02 | +0.06 USDT | 3.24% |

### Decision

ADX 30 reduces out-of-sample drawdown and produces a marginal positive result, but it fails the development gate. It is **not** promoted into the dry-run configuration. This experiment only shows that stronger trend filtering is worth investigating; it does not establish a viable strategy.

## Experiment 002 — 1H RSI momentum threshold

Only the lower bound of the 1H RSI entry filter was changed. The baseline range is 45–65. The candidates use 50–65 and 55–65; ADX remains 20 and every other decision variable is unchanged.

| RSI range | Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 45–65 (baseline) | Development | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| 45–65 (baseline) | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 45–65 (baseline) | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |
| 50–65 | Development | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| 50–65 | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 50–65 | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |
| 55–65 | Development | 164 | -20.72% | 0.64 | -1.26 USDT | 21.00% |
| 55–65 | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 55–65 | Out-of-sample | 40 | -2.06% | 0.86 | -0.51 USDT | 7.77% |

### Decision

RSI 50 is identical to the baseline, which means every baseline entry already had RSI above 50 after the other filters were applied. RSI 55 removes only three development and two out-of-sample trades. It improves the latest out-of-sample result, but development remains materially negative and validation still has only four trades. Neither setting is promoted to dry-run.

## Experiment 003 — 1H close breakout confirmation

This experiment adds one independent price-momentum condition: the 1H close must be greater than the highest high of the preceding 10 or 20 completed candles. The baseline uses no breakout condition. All other filters, risk settings, and test periods are unchanged.

| Breakout lookback | Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| None (baseline) | Development | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| None (baseline) | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| None (baseline) | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |
| 10 candles | Development | 100 | -13.12% | 0.65 | -1.31 USDT | 15.01% |
| 10 candles | Validation | 3 | +0.53% | 1.76 | +1.76 USDT | 0.68% |
| 10 candles | Out-of-sample | 24 | -0.47% | 0.94 | -0.20 USDT | 3.11% |
| 20 candles | Development | 71 | -8.21% | 0.69 | -1.16 USDT | 9.82% |
| 20 candles | Validation | 2 | +1.12% | 12.03 | +5.59 USDT | 0.10% |
| 20 candles | Out-of-sample | 11 | -0.09% | 0.97 | -0.08 USDT | 1.40% |

### Decision

The 20-candle condition is the strongest of the tested filters: it reduces loss and drawdown across development and out-of-sample periods. It remains negative in both periods, and its two validation trades make the positive validation result unusable as evidence. It is **not** promoted into dry-run. The result supports continuing to investigate entry quality, with a new independent signal rather than more threshold tuning.

The next controlled experiment should test a higher-timeframe price-structure confirmation, for example a 4H higher-high/higher-low rule. Position sizing, stop-loss, take-profit, pair universe, and external data stay fixed until a candidate passes the metric gate.

## Experiment 004 — 4H market structure and composite entry quality

The market-structure candidate requires the completed 4H candle to have both a higher high and a higher low than the preceding 4H candle. The composite candidate adds that rule to the 20-candle 1H breakout condition from Experiment 003.

| Entry condition | Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 4H higher-high + higher-low | Development | 120 | -17.56% | 0.59 | -1.46 USDT | 19.39% |
| 4H higher-high + higher-low | Validation | 3 | +0.69% | 2.19 | +2.31 USDT | 0.57% |
| 4H higher-high + higher-low | Out-of-sample | 28 | +0.52% | 1.06 | +0.18 USDT | 4.49% |
| Structure + 1H 20-candle breakout | Development | 47 | -5.39% | 0.69 | -1.15 USDT | 9.71% |
| Structure + 1H 20-candle breakout | Validation | 2 | +1.12% | 12.03 | +5.59 USDT | 0.10% |
| Structure + 1H 20-candle breakout | Out-of-sample | 9 | +0.20% | 1.08 | +0.23 USDT | 1.40% |

### Decision

The composite condition is the current least-bad candidate: it materially reduces loss and drawdown, and is positive out-of-sample. It remains negative in development and has only two validation trades, so it is not a live or dry-run promotion candidate. The small trade sample means further threshold tuning would be especially prone to overfitting.

Pair diagnostics reinforce that conclusion. In the composite development period, ETH/USDT had 21 trades and +4.49 USDT while BTC/USDT had 26 trades and -58.37 USDT. In out-of-sample, the result reversed: BTC/USDT had 5 trades and +15.40 USDT, while ETH/USDT had 4 trades and -13.37 USDT. Neither pair can be removed on this evidence.

## Experiment 005 — defensive time stop

The baseline custom exit was supplemented with a time stop that closes a position only when it remains non-positive after 24 or 48 hours. This was tested after the exit-reason diagnostic showed stop-loss exits were the main source of loss.

| Time stop | Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| None (baseline) | Development | 167 | -20.97% | 0.64 | -1.26 USDT | 21.26% |
| 24 hours | Development | 180 | -21.91% | 0.63 | -1.22 USDT | 22.52% |
| 24 hours | Validation | 4 | +0.16% | 1.14 | +0.40 USDT | 1.16% |
| 24 hours | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |
| 48 hours | Development | 173 | -21.17% | 0.64 | -1.22 USDT | 21.46% |
| 48 hours | Validation | 4 | +0.10% | 1.09 | +0.26 USDT | 1.16% |
| 48 hours | Out-of-sample | 42 | -2.61% | 0.83 | -0.62 USDT | 8.74% |

### Decision

Neither time stop improves the strategy; the 24-hour condition worsens development drawdown and the 48-hour condition produces no meaningful out-of-sample change. This exit branch is closed. The next research phase should add a genuinely independent data source or a different strategy family, rather than continuing to tune filters around the same EMA/RSI/MACD signal.

## Experiment 006 — 1H pullback within 4H trend

This experiment tests a separate entry hypothesis. Within the same 4H bullish regime, a position is opened only after price pulls back below the 1H EMA 20 while remaining above EMA 50, RSI is 35–50, and the MACD histogram begins to recover. The unchanged ATR-based risk and exit model make the entry rule the only variable under test.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 132 | -13.09% | 0.72 | -0.99 USDT | 14.41% |
| Validation | 8 | -1.57% | 0.56 | -1.97 USDT | 3.54% |
| Out-of-sample | 38 | -5.34% | 0.60 | -1.40 USDT | 9.07% |

### Decision

The pullback hypothesis is rejected. It increases sample size versus the sparse breakout composite, but it is negative in all three periods and exceeds the 5% drawdown limit in development and out-of-sample. It is retained only as reproducible research code and cannot replace the conservative paper strategy.

## Experiment 007 — 1H EMA reclaim inside stronger 4H trend

This continuation hypothesis requires a 4H bullish EMA 50/200 regime with ADX above 25, then enters only when a 1H candle reclaims EMA 20 while EMA 20 remains above EMA 50. RSI, MACD, and volume-average filters are deliberately omitted. This tests a lower-frequency price-trend rule rather than another variant of the prior oscillator logic.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 187 | -17.60% | 0.72 | -0.94 USDT | 19.74% |
| Validation | 16 | -0.97% | 0.85 | -0.61 USDT | 4.77% |
| Out-of-sample | 50 | -10.05% | 0.49 | -2.01 USDT | 12.91% |

### Decision

The EMA reclaim continuation hypothesis is rejected. It provides sufficient trade count in development and out-of-sample, so the negative profit factors and expectancy are meaningful rather than a sample-size artifact. It has the weakest out-of-sample result tested so far and exceeds the drawdown gate in two periods. Further tuning of this family is not justified.

## Experiment 008 — range mean reversion

This is a separate hypothesis from the rejected trend-following families. It enters only when 4H price is above the long-term EMA baseline but ADX is below 20, while the 1H close falls below the lower 20-period Bollinger Band with RSI below 30. Exit is at the Bollinger midpoint or RSI 55; ATR stop and all cost assumptions remain unchanged.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 60 | -11.22% | 0.46 | -1.87 USDT | 13.10% |
| Validation | 5 | -1.56% | 0.17 | -3.12 USDT | 1.56% |
| Out-of-sample | 18 | +1.97% | 1.72 | +1.09 USDT | 0.89% |

### Decision

The range mean-reversion hypothesis is rejected. Although the latest out-of-sample period is positive, it has only 18 trades and both development and validation are materially negative. The development drawdown also exceeds the 5% gate. This strategy remains research-only and cannot replace the paper strategy. The experiment demonstrates that neither the currently tested trend-following nor simple oversold-reversal family is robust across the three periods.

## Experiment 009 — active strategy with trailing stop

This validates the MVP trailing-stop behavior after first target: after profit reaches 1.5R, the stop follows price at one initial-risk fraction below the current rate, never below entry. The entry rules, 1.5R partial take-profit, 2.5R target, fees, and all evaluation periods are unchanged.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 174 | -28.37% | 0.50 | -1.63 USDT | 28.37% |
| Validation | 4 | -0.10% | 0.92 | -0.24 USDT | 1.16% |
| Out-of-sample | 44 | -3.66% | 0.75 | -0.83 USDT | 8.37% |

### Decision

The trailing-stop implementation is technically validated by the historical runs, which record trailing-stop exits, but it worsens the existing rejected baseline in development and remains negative out-of-sample. It is not evidence for a live promotion. It remains part of the paper MVP risk behavior while the quant research continues; any future frozen candidate must be evaluated from scratch with this exit logic.

## Experiment 010 — Donchian breakout trend family

This experiment tests a clean channel-breakout hypothesis rather than the oscillator-driven baseline. It enters after a 20-hour breakout only during a 4H bullish EMA regime with ADX above 25; it exits below the prior 10-hour channel low. The inherited ATR stop, partial take-profit, and trailing-stop behavior are unchanged.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 296 | -42.47% | 0.47 | -1.43 USDT | 42.47% |
| Validation | 19 | -5.09% | 0.31 | -2.68 USDT | 5.83% |
| Out-of-sample | 57 | -8.35% | 0.58 | -1.47 USDT | 9.45% |

### Decision

The Donchian breakout family is rejected. It has adequate samples in development and out-of-sample, and the consistently negative profit factors, expectancy, and drawdown make the failure decisive. Further channel-length or ADX tuning would not be justified. Across the tested momentum, pullback, mean-reversion, and breakout families, the BTC/ETH-only 1H universe has not produced a robust candidate. The next research phase must expand the data or universe under a pre-declared protocol before further strategy changes.

## Experiment 011 — expanded liquid universe

This experiment changes only the research universe from BTC/ETH to BTC/ETH/SOL/BNB. It uses the same 1H/4H baseline, trailing-stop implementation, fee assumptions, and max-two-position configuration. SOL and BNB historical candles were downloaded directly from Binance; the production whitelist remains BTC/ETH.

| Period | Trades | Return | Profit factor | Expectancy | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 344 | -40.70% | 0.56 | -1.18 USDT | 42.60% |
| Validation | 17 | -0.74% | 0.87 | -0.44 USDT | 3.36% |
| Out-of-sample | 79 | -10.37% | 0.63 | -1.31 USDT | 15.01% |

### Decision

The expanded universe is rejected. More liquid pairs increase sample size but do not create a positive edge: every evaluation period remains negative and development/out-of-sample drawdown is far above the gate. SOL and BNB are not promoted to paper mode. Further work must use independent, pre-declared data features or a strategy family with a documented economic hypothesis; adding pairs or tuning thresholds is closed for this baseline.
