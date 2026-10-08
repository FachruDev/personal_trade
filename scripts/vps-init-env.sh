#!/usr/bin/env bash
# Create a fresh .env for a paper-trading VPS with newly generated secrets.
#
# Secrets are created on the VPS and never printed. Optional provider keys (Binance, FRED, NewsAPI, ...)
# stay empty: paper trading needs none of them. Refuses to overwrite an existing .env.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="$root/.env.example"
target="$root/.env"

if [ -e "$target" ]; then
    echo "Refusing to overwrite the existing $target" >&2
    exit 1
fi
command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }
if command -v python3 >/dev/null 2>&1; then py=python3; elif command -v python >/dev/null 2>&1; then py=python; else echo "python3 is required" >&2; exit 1; fi

# Windows (Git Bash) hands native programs Windows paths; Linux needs no conversion.
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

umask 077
"$py" - "$(host_path "$template")" "$(host_path "$target")" \
    "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" <<'PY'
import re
import sys

template, target, postgres_password, control_token, freqtrade_password, jwt_secret = sys.argv[1:7]
text = open(template, encoding="utf-8").read().replace("\r\n", "\n")


def set_value(body: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if not pattern.search(body):
        raise SystemExit(f"{key} is missing from .env.example")
    return pattern.sub(lambda _match: f"{key}={value}", body, count=1)


# The same Postgres password appears in POSTGRES_PASSWORD and inside DATABASE_URL.
text = text.replace("replace-with-a-strong-local-password", postgres_password)
text = set_value(text, "BOT_CONTROL_TOKEN", control_token)
text = set_value(text, "FREQTRADE_API_PASSWORD", freqtrade_password)
text = set_value(text, "FREQTRADE_JWT_SECRET", jwt_secret)
text = set_value(text, "TRADING_ENVIRONMENT", "paper")
# Daily trend strategy in paper mode; see docs/daily-trend-validation.md.
text = set_value(text, "FREQTRADE_PROFILE_CONFIG", "/freqtrade/user_data/config/profiles/paper-daily-trend.json")
text = set_value(text, "FREQTRADE_STRATEGY", "DailyTrendVolStrategy")
text = set_value(text, "PAPER_STRATEGY_SOURCE_FILE", "/freqtrade/user_data/strategies/DailyTrendVolStrategy.py")
text = set_value(text, "PAPER_RUN_REVISION", "daily-trend-v2")
open(target, "w", encoding="utf-8", newline="\n").write(text)
PY

chmod 600 "$target"
echo "Created $target (mode 600) with generated secrets. Nothing was printed."
echo "Next: bash scripts/vps-preflight.sh"
