#!/usr/bin/env bash
# Summarize the paper run: evidence status from the API plus trades from the Freqtrade database.
#   bash scripts/paper-run-summary.sh          readable text
#   bash scripts/paper-run-summary.sh --json   machine-readable (also written by the export script)
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mode="text"
[ "${1:-}" = "--json" ] && mode="json"
if command -v python3 >/dev/null 2>&1; then py=python3; elif command -v python >/dev/null 2>&1; then py=python; else echo "python3 is required" >&2; exit 1; fi

paper_run="$(curl -fsS --max-time 5 http://127.0.0.1:8000/v1/paper-run 2>/dev/null || echo null)"
events="$(curl -fsS --max-time 5 'http://127.0.0.1:8000/v1/decisions/summary' 2>/dev/null || echo null)"

if [ -n "$(docker compose ps --status running -q freqtrade 2>/dev/null)" ]; then
    trades="$(docker compose exec -T freqtrade python - <<'PY'
import glob
import json
import sqlite3

summary = {"database": None, "open": [], "closed": {"count": 0, "profit_abs": 0.0, "wins": 0}}
paths = [p for p in glob.glob("/freqtrade/user_data/**/*.sqlite", recursive=True) if "/.export-" not in p]
if paths:
    summary["database"] = paths[0]
    db = sqlite3.connect(f"file:{paths[0]}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    for row in db.execute("select pair, amount, stake_amount, open_rate, open_date from trades where is_open = 1 order by pair"):
        summary["open"].append(dict(row))
    row = db.execute(
        "select count(*) n, coalesce(sum(close_profit_abs), 0) p, coalesce(sum(close_profit_abs > 0), 0) w "
        "from trades where is_open = 0"
    ).fetchone()
    summary["closed"] = {"count": row["n"], "profit_abs": round(row["p"], 4), "wins": row["w"]}
print(json.dumps(summary))
PY
)"
else
    trades="null"
fi

PAPER_RUN="$paper_run" EVENTS="$events" TRADES="$trades" MODE="$mode" "$py" - <<'PY'
import json
import os

def load(name):
    try:
        return json.loads(os.environ[name])
    except ValueError:
        return None

paper_run, events, trades = load("PAPER_RUN"), load("EVENTS"), load("TRADES")
result = {
    "paper_run": paper_run,
    "audit_event_counts": (events or {}).get("event_counts"),
    "trades": trades,
}
if os.environ["MODE"] == "json":
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit
print("Paper run")
if paper_run:
    for key in ("status", "strategy", "revision", "profile", "elapsed_days", "required_days", "observations", "coverage_ratio", "first_observed_at", "last_observed_at"):
        print(f"  {key}: {paper_run.get(key)}")
else:
    print("  API not reachable")
print("Trades")
if trades:
    print(f"  closed: {trades['closed']['count']} (profit {trades['closed']['profit_abs']} USDT, wins {trades['closed']['wins']})")
    print(f"  open: {len(trades['open'])}")
    for position in trades["open"]:
        print(f"    {position['pair']}: stake {position['stake_amount']:.2f} USDT since {position['open_date']}")
else:
    print("  Freqtrade container not running")
if result["audit_event_counts"]:
    print("Audit events:", ", ".join(f"{k}={v}" for k, v in sorted(result["audit_event_counts"].items())))
PY
