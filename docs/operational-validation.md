# Operational Validation Record

## 2 October 2026 — Paper-control stop and resume

Scope: local Docker paper environment only. No live profile, leverage, or real order was enabled.

| Check | Evidence | Result |
| --- | --- | --- |
| Emergency stop | `POST /v1/bot/stop` returned `stop_requested` through the local authenticated control path. | Pass |
| Entry gate | Redis key `trading:kill-switch` was `enabled` immediately after stop. | Pass |
| Resume | `POST /v1/bot/resume` returned `resume_requested`. | Pass |
| Entry gate restored | Redis kill-switch was absent after resume. | Pass |
| Auditability | `bot_stop_requested` and `bot_resume_requested` both appeared in `GET /v1/decisions`. | Pass |
| Service recovery | API, PostgreSQL, Redis, Freqtrade, and dashboard were running after the test. | Pass |

## 2 October 2026 — Fail-closed dependency outages

Scope: local Docker paper environment only. Each dependency was stopped briefly and restored before the next check. The Freqtrade strategy rejects an entry whenever its control request receives a non-success response or times out.

| Check | Evidence | Result |
| --- | --- | --- |
| PostgreSQL outage | `GET /internal/kill-switch` from the Freqtrade container timed out while PostgreSQL was unavailable; this follows the strategy's fail-closed rejection path. It returned `200` after recovery. | Pass |
| Redis outage | The same control request was unavailable while Redis was stopped and returned `200` after recovery. | Pass |
| Control API outage | The control request was unavailable while API was stopped and returned `200` after recovery. | Pass |
| Dependency recovery | PostgreSQL and Redis health checks recovered; API health, Freqtrade, and dashboard were healthy after every restoration. | Pass |

## 2 October 2026 — Freqtrade restart

| Check | Evidence | Result |
| --- | --- | --- |
| Execution-engine restart | The `freqtrade` service restarted in the paper environment. | Pass |
| Control recovery | `GET /v1/operational-state` reported `paper`, `kill_switch_enabled: false`, and `freqtrade_reachable: true` after restart. | Pass |

## 2 October 2026 — Binance public-market connectivity

| Check | Evidence | Result |
| --- | --- | --- |
| Public REST reachability | `GET /v1/market/binance/status` reached the Binance public exchange-information endpoint. | Pass |
| Pair status | BTCUSDT and ETHUSDT both returned `TRADING`. | Pass |
| Host clock | Freqtrade reported a 3.9-second difference from Binance during paper startup. Market status now exposes `clock_drift_seconds` and `clock_synchronized`; synchronize the Windows host clock before any release. | Open |
| Safe API fallback | API unit test simulates a Binance connection error and verifies `reachable: false`, no tradable pairs, and `clock_synchronized: false`. | Pass |

The broader paper-release checklist still requires provider failure testing and a deliberately simulated Binance-connectivity failure, as well as a qualifying frozen strategy and extended dry-run evidence.
