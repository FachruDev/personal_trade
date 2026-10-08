#!/usr/bin/env bash
# Check that a Linux host is ready for an unattended 56-day paper run. Exits 1 if any check fails.
#   bash scripts/vps-preflight.sh
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root" || exit 1
failures=0
warnings=0

pass() { printf '  [ ok ] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; failures=$((failures + 1)); }
warn() { printf '  [warn] %s\n' "$1"; warnings=$((warnings + 1)); }

echo "Tools"
for tool in git curl python3 openssl; do
    if command -v "$tool" >/dev/null 2>&1; then pass "$tool installed"; else fail "$tool is not installed"; fi
done
if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose v2 ($(docker compose version --short))"
else
    fail "Docker Compose v2 is not available (install the docker-compose-plugin)"
fi
if docker info >/dev/null 2>&1; then
    pass "Docker daemon reachable by this user"
else
    fail "Cannot talk to the Docker daemon (is it running, and is this user in the docker group?)"
fi
if command -v systemctl >/dev/null 2>&1 && [ "$(systemctl is-enabled docker 2>/dev/null)" = "enabled" ]; then
    pass "Docker starts at boot"
else
    warn "Could not confirm Docker starts at boot (sudo systemctl enable docker)"
fi

echo "Configuration"
if [ -f .env ]; then
    pass ".env exists"
    mode="$(stat -c %a .env 2>/dev/null || echo unknown)"
    if [ "$mode" = "600" ]; then pass ".env permissions are 600"; else warn ".env permissions are $mode (chmod 600 .env)"; fi
    if grep -qiE 'replace-with|change-me|local-development' .env; then
        fail ".env still contains placeholder secrets (run scripts/vps-init-env.sh on a fresh host)"
    else
        pass ".env has no placeholder secrets"
    fi
    if grep -qE '^TRADING_ENVIRONMENT=paper$' .env; then pass "TRADING_ENVIRONMENT=paper"; else fail "TRADING_ENVIRONMENT must be paper"; fi
    for key in FREQTRADE_PROFILE_CONFIG FREQTRADE_STRATEGY PAPER_STRATEGY_SOURCE_FILE PAPER_RUN_REVISION; do
        printf '         %s=%s\n' "$key" "$(grep -E "^$key=" .env | head -n1 | cut -d= -f2-)"
    done
else
    fail ".env is missing (bash scripts/vps-init-env.sh)"
fi
if grep -E '^\s*ports:' compose.yaml | grep -v '127.0.0.1' >/dev/null; then
    fail "compose.yaml publishes a port that is not bound to 127.0.0.1"
else
    pass "all published ports are bound to 127.0.0.1"
fi

echo "Clock"
if command -v timedatectl >/dev/null 2>&1; then
    synced="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo unknown)"
    if [ "$synced" = "yes" ]; then pass "system clock is NTP-synchronized"; else warn "NTPSynchronized=$synced (sudo timedatectl set-ntp true, or install chrony)"; fi
fi
server_ms="$(curl -fsS --max-time 10 https://api.binance.com/api/v3/time 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["serverTime"])' 2>/dev/null || true)"
if [ -n "$server_ms" ]; then
    drift_ms="$(python3 -c "import time,sys; print(abs(int(time.time()*1000) - int(sys.argv[1])))" "$server_ms")"
    if [ "$drift_ms" -le 2000 ]; then pass "clock drift versus Binance is ${drift_ms} ms (limit 2000)"; else fail "clock drift versus Binance is ${drift_ms} ms (limit 2000)"; fi
else
    fail "could not reach api.binance.com to measure clock drift (network or regional block)"
fi

echo "Storage and memory"
mkdir -p freqtrade/db freqtrade/logs freqtrade/data
for dir in freqtrade/db freqtrade/logs freqtrade/data; do
    owner="$(stat -c %u "$dir" 2>/dev/null || echo unknown)"
    if [ "$owner" = "1000" ]; then
        pass "$dir is owned by uid 1000 (the Freqtrade container user)"
    else
        fail "$dir is owned by uid $owner; run: sudo chown -R 1000:1000 freqtrade"
    fi
done
free_kb="$(df -Pk "$root" | awk 'NR==2 {print $4}')"
if [ "${free_kb:-0}" -ge 5242880 ]; then pass "free disk $((free_kb / 1024 / 1024)) GiB"; else fail "free disk below 5 GiB"; fi
mem_mb="$(free -m 2>/dev/null | awk '/^Mem:/ {print $7}')"
swap_mb="$(free -m 2>/dev/null | awk '/^Swap:/ {print $2}')"
if [ "${mem_mb:-0}" -ge 1500 ] || [ "${swap_mb:-0}" -ge 1024 ]; then
    pass "memory available ${mem_mb:-?} MiB, swap ${swap_mb:-0} MiB (the web image build needs about 1.5 GiB)"
else
    warn "low memory (${mem_mb:-?} MiB available, swap ${swap_mb:-0} MiB): add 2 GiB swap before building the web image"
fi

echo "Network exposure"
if command -v ufw >/dev/null 2>&1; then
    if ufw status 2>/dev/null | grep -q "Status: active"; then pass "ufw firewall is active"; else warn "ufw is installed but inactive (allow SSH first, then: sudo ufw enable)"; fi
else
    warn "no ufw found; make sure the provider firewall only allows SSH"
fi

echo
if [ "$failures" -gt 0 ]; then
    echo "$failures check(s) failed, $warnings warning(s)."
    exit 1
fi
echo "All checks passed ($warnings warning(s))."
