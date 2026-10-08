#!/usr/bin/env bash
# Linux/macOS counterpart of export-portable-state.ps1. Writes the same
# "trading-bot-portable-state/v1" package, so a package made on a VPS can be restored on Windows with
# import-portable-state.ps1 and the other way round.
#
#   bash scripts/export-portable-state.sh [--destination DIR] [--include-historical-data]
#
# The PostgreSQL stack must be running. The Freqtrade trade database is snapshotted consistently when the
# bot is running, or copied as-is when it is stopped. No .env, key, or password is ever copied.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
destination="$root/portable-state"
include_historical=0

usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
    case "$1" in
        --destination) destination="${2:?--destination needs a directory}"; shift 2 ;;
        --include-historical-data) include_historical=1; shift ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
if command -v python3 >/dev/null 2>&1; then py=python3; elif command -v python >/dev/null 2>&1; then py=python; else echo "python3 is required" >&2; exit 1; fi

# Windows (Git Bash) hands docker.exe Windows paths; Linux needs no conversion.
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
compose() { docker compose "$@"; }
postgres_id="$(compose ps -q postgres)"
if [ -z "$postgres_id" ]; then
    echo "The PostgreSQL container is not running. Start the stack before exporting portable state." >&2
    exit 1
fi

mkdir -p "$destination"
destination="$(cd "$destination" && pwd)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dump_name="trading-bot-postgres-$timestamp.dump"

# A custom pg_dump archive keeps every audit/context table and no credentials.
# The variables are expanded inside the container on purpose (single quotes).
# shellcheck disable=SC2016
compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file=/tmp/trading-bot-portable-state.dump'
docker cp "$postgres_id:/tmp/trading-bot-portable-state.dump" "$(host_path "$destination/$dump_name")"
compose exec -T postgres rm -f /tmp/trading-bot-portable-state.dump

# Freqtrade trade database(s).
trade_files=()
if [ -n "$(compose ps --status running -q freqtrade)" ]; then
    # Online snapshot through SQLite's backup API: a plain file copy of a live WAL database can be torn.
    compose exec -T freqtrade python - <<'PY'
import glob
import os
import sqlite3

for source in glob.glob("/freqtrade/user_data/**/*.sqlite", recursive=True):
    name = os.path.basename(source)
    if name.startswith(".export-"):
        continue
    target = os.path.join(os.path.dirname(source), ".export-" + name)
    reader = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    writer = sqlite3.connect(target)
    reader.backup(writer)
    writer.close()
    reader.close()
PY
    while IFS= read -r snapshot; do
        [ -n "$snapshot" ] || continue
        relative="${snapshot#"$root/freqtrade/"}"
        final_relative="$(dirname "$relative")/$(basename "$relative" | sed 's/^\.export-//')"
        mkdir -p "$destination/freqtrade/$(dirname "$final_relative")"
        cp -f "$snapshot" "$destination/freqtrade/$final_relative"
        trade_files+=("freqtrade/$final_relative")
    done < <(find "$root/freqtrade" -type f -name '.export-*.sqlite' 2>/dev/null)
    compose exec -T freqtrade sh -c 'find /freqtrade/user_data -type f -name ".export-*.sqlite" -delete'
else
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        relative="${file#"$root/freqtrade/"}"
        mkdir -p "$destination/freqtrade/$(dirname "$relative")"
        cp -f "$file" "$destination/freqtrade/$relative"
        trade_files+=("freqtrade/$relative")
    done < <(find "$root/freqtrade" -type f -name '*.sqlite*' ! -name '.export-*' 2>/dev/null)
fi

if [ "$include_historical" = 1 ] && [ -d "$root/freqtrade/data" ]; then
    mkdir -p "$destination/freqtrade"
    cp -R "$root/freqtrade/data" "$destination/freqtrade/"
fi

paper_run="$(curl -fsS --max-time 5 http://127.0.0.1:8000/v1/paper-run 2>/dev/null || echo null)"
git_revision="$(git -C "$root" rev-parse HEAD 2>/dev/null || true)"

DUMP_NAME="$dump_name" INCLUDE_HISTORICAL="$include_historical" GIT_REVISION="$git_revision" \
PAPER_RUN="$paper_run" TRADE_FILES="$(printf '%s\n' ${trade_files[@]+"${trade_files[@]}"})" \
MANIFEST_PATH="$(host_path "$destination/manifest.json")" "$py" - <<'PY'
import datetime
import json
import os

try:
    paper_run = json.loads(os.environ["PAPER_RUN"])
except ValueError:
    paper_run = None
manifest = {
    "format": "trading-bot-portable-state/v1",
    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "postgres_dump": os.environ["DUMP_NAME"],
    "freqtrade_trade_files": [line for line in os.environ["TRADE_FILES"].splitlines() if line],
    "historical_data_included": os.environ["INCLUDE_HISTORICAL"] == "1",
    "source_revision": os.environ.get("GIT_REVISION") or None,
    "paper_run": paper_run,
    "secrets_included": False,
    "exported_by": "export-portable-state.sh",
}
with open(os.environ["MANIFEST_PATH"], "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
PY

# Human-readable results, best effort: the export is still valid without it.
bash "$root/scripts/paper-run-summary.sh" --json >"$destination/results-summary.json" 2>/dev/null || rm -f "$destination/results-summary.json"

echo "Exported to $destination"
echo "  postgres_dump: $dump_name"
echo "  freqtrade trade files: ${#trade_files[@]}"
echo "  secrets_included: false"
