#!/usr/bin/env bash
# Take a portable-state backup outside the repository and keep only the newest N.
#   bash scripts/vps-backup.sh [--keep 14] [--dir ~/trading-bot-backups]
#
# Example cron entry (daily 03:17, log kept next to the backups):
#   17 3 * * * cd /home/USER/trading_bot && bash scripts/vps-backup.sh --keep 14 >> /home/USER/trading-bot-backups/backup.log 2>&1
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
keep=14
base="${BACKUP_DIR:-$HOME/trading-bot-backups}"

while [ $# -gt 0 ]; do
    case "$1" in
        --keep) keep="${2:?--keep needs a number}"; shift 2 ;;
        --dir) base="${2:?--dir needs a directory}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
case "$keep" in '' | *[!0-9]*) echo "--keep must be a positive integer" >&2; exit 2 ;; esac
[ "$keep" -ge 1 ] || { echo "--keep must be at least 1" >&2; exit 2; }
[ -n "$base" ] && [ "$base" != "/" ] || { echo "Refusing to use '$base' as the backup directory" >&2; exit 2; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$base"
bash "$root/scripts/export-portable-state.sh" --destination "$base/$stamp"
echo "Backup written to $base/$stamp"

# Prune: only directories named like a timestamp are ever removed, oldest first.
mapfile -t backups < <(find "$base" -mindepth 1 -maxdepth 1 -type d -name '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z' | sort)
excess=$((${#backups[@]} - keep))
if [ "$excess" -gt 0 ]; then
    for old in "${backups[@]:0:$excess}"; do
        rm -rf -- "$old"
        echo "Pruned $old"
    done
fi
