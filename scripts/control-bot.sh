#!/usr/bin/env bash
# Linux counterpart of control-bot.ps1: emergency stop or resume of new entries through the control API.
# The control token never leaves the API container, so it does not enter your shell history.
#   bash scripts/control-bot.sh stop
#   bash scripts/control-bot.sh resume
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths

action="${1:-}"
case "$action" in stop | resume) ;; *) echo "Usage: control-bot.sh stop|resume" >&2; exit 2 ;; esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
docker compose exec -T -e "BOT_ACTION=$action" api python -c '
import json
import os
import urllib.request

action = os.environ["BOT_ACTION"]
request = urllib.request.Request(
    f"http://localhost:8000/v1/bot/{action}",
    method="POST",
    headers={"X-Bot-Control-Token": os.environ["BOT_CONTROL_TOKEN"]},
)
print(json.dumps(json.loads(urllib.request.urlopen(request).read()), indent=2))
'
