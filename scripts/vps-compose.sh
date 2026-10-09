#!/usr/bin/env bash
# Run docker compose with the VPS overrides, from any directory.
#   bash scripts/vps-compose.sh up -d --build
#   bash scripts/vps-compose.sh ps
#
# .env.example supplies defaults and .env (if present) overrides them for compose interpolation, so
# API_PORT and FREQTRADE_UI_PORT set in .env take effect. Services still read .env themselves.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
env_args=(--env-file .env.example)
[ -f .env ] && env_args+=(--env-file .env)
exec docker compose -f compose.yaml -f compose.vps.yaml "${env_args[@]}" "$@"
