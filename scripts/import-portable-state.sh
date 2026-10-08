#!/usr/bin/env bash
# Linux/macOS counterpart of import-portable-state.ps1. Restores a "trading-bot-portable-state/v1"
# package, whether it was made by export-portable-state.sh or export-portable-state.ps1.
#
#   bash scripts/import-portable-state.sh --source ./portable-state --force
#
# Replaces the PostgreSQL application data and the Freqtrade trade database. Refuses to run while the api,
# web, or freqtrade service is running, so a live database is never overwritten by an older snapshot.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
source_dir=""
force=0

usage() { sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
    case "$1" in
        --source) source_dir="${2:?--source needs a directory}"; shift 2 ;;
        --force) force=1; shift ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$source_dir" ] || { echo "--source is required" >&2; exit 2; }
if [ "$force" != 1 ]; then
    echo "Restoring replaces the target PostgreSQL application data. Re-run with --force only on a prepared host." >&2
    exit 1
fi
if command -v python3 >/dev/null 2>&1; then py=python3; elif command -v python >/dev/null 2>&1; then py=python; else echo "python3 is required" >&2; exit 1; fi

source_dir="$(cd "$source_dir" && pwd)"
manifest="$source_dir/manifest.json"
[ -f "$manifest" ] || { echo "Portable-state manifest.json was not found." >&2; exit 1; }

# Windows (Git Bash) hands docker.exe Windows paths; Linux needs no conversion.
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

read_manifest() {
    "$py" - "$(host_path "$manifest")" "$1" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8-sig"))
field = sys.argv[2]
# Write bytes with a bare newline: Windows Python would otherwise emit CR+LF and the bash loop below
# would read file names ending in a carriage return.
out = sys.stdout.buffer
newline = chr(10)
if field == "format":
    out.write((manifest.get("format", "") + newline).encode())
elif field == "dump":
    out.write((manifest.get("postgres_dump", "") + newline).encode())
elif field == "trade_files":
    for entry in manifest.get("freqtrade_trade_files") or []:
        out.write((entry + newline).encode())
PY
}

[ "$(read_manifest format)" = "trading-bot-portable-state/v1" ] || { echo "Unsupported portable-state format." >&2; exit 1; }
dump_name="$(read_manifest dump)"
dump_path="$source_dir/$dump_name"
[ -n "$dump_name" ] && [ -f "$dump_path" ] || { echo "PostgreSQL dump referenced by the manifest was not found." >&2; exit 1; }

for service in api web freqtrade; do
    if [ -n "$(docker compose ps --status running -q "$service")" ]; then
        echo "Stop the running $service service before restoring portable state." >&2
        exit 1
    fi
done

docker compose up -d postgres redis
ready=0
for _ in $(seq 1 30); do
    if docker compose exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 2
done
[ "$ready" = 1 ] || { echo "PostgreSQL did not become ready for restore." >&2; exit 1; }

postgres_id="$(docker compose ps -q postgres)"
[ -n "$postgres_id" ] || { echo "PostgreSQL container is unavailable." >&2; exit 1; }
docker cp "$(host_path "$dump_path")" "$postgres_id:/tmp/trading-bot-portable-state.dump"
docker compose exec -T postgres sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/trading-bot-portable-state.dump'
docker compose exec -T postgres rm -f /tmp/trading-bot-portable-state.dump

restored=0
while IFS= read -r relative; do
    relative="${relative%$'\r'}"
    [ -n "$relative" ] || continue
    source_file="$source_dir/$relative"
    target_file="$root/freqtrade/${relative#freqtrade/}"
    [ -f "$source_file" ] || { echo "Freqtrade trade file listed in manifest is missing: $relative" >&2; exit 1; }
    mkdir -p "$(dirname "$target_file")"
    # A stale -wal/-shm left by an earlier database would be replayed onto the restored file and corrupt it.
    rm -f "$target_file-wal" "$target_file-shm"
    cp -f "$source_file" "$target_file"
    # Trade data holds no secrets; the Freqtrade container user (uid 1000) must be able to write it.
    chmod 666 "$target_file"
    restored=$((restored + 1))
done < <(read_manifest trade_files)

echo "Restored PostgreSQL dump: $dump_name"
echo "Restored Freqtrade trade files: $restored"
echo "Next: create .env securely if this is a new host, then: bash scripts/vps-compose.sh up -d"
