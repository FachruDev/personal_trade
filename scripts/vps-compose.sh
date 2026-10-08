#!/usr/bin/env bash
# Run docker compose with the VPS overrides, from any directory.
#   bash scripts/vps-compose.sh up -d --build
#   bash scripts/vps-compose.sh ps
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
exec docker compose -f compose.yaml -f compose.vps.yaml --env-file .env.example "$@"
