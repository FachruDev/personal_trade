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

The next controlled experiment will evaluate the 1H momentum entry filter while retaining ADX 20 as the baseline. Risk sizing, stop-loss, take-profit, pair universe, and external data remain fixed until a candidate passes all periods.
