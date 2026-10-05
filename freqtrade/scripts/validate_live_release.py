"""Fail closed when Compose is configured for a limited-live release.

This is a startup gate, not evidence that the strategy is profitable. The
operator must still satisfy the full checklist and preserve the reviewed
approval record outside Git.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


MAX_CLOCK_DRIFT_SECONDS = 2.0


def fail(message: str) -> None:
    print(f"Live release validation failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        fail(f"{label} is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{label} is invalid: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object")
    return value


def fetch_binance_clock_drift_seconds() -> float:
    """Read Binance public server time and return absolute local clock drift."""
    base_url = os.getenv("BINANCE_PUBLIC_BASE_URL", "https://api.binance.com").rstrip("/")
    try:
        with urlopen(f"{base_url}/api/v3/time", timeout=10) as response:  # noqa: S310 - configured Binance public URL
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Binance server time is unavailable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Binance server time response is invalid")
    try:
        server_time_ms = float(payload["serverTime"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Binance server time response is missing serverTime") from exc
    if not math.isfinite(server_time_ms) or server_time_ms <= 0:
        raise ValueError("Binance serverTime is invalid")
    return abs((time.time() * 1_000 - server_time_ms) / 1_000)


def validation_errors(
    profile: dict,
    approval: dict,
    quant_report_path: Path | None,
    strategy_source_path: Path | None,
    clock_drift_fetcher=fetch_binance_clock_drift_seconds,
) -> list[str]:
    errors: list[str] = []
    if profile.get("dry_run") is not False:
        errors.append("live profile must explicitly set dry_run=false")
    if profile.get("max_open_trades") != 1:
        errors.append("live profile must allow exactly one open trade")
    try:
        tradable_balance_ratio = float(profile.get("tradable_balance_ratio", 1))
    except (TypeError, ValueError):
        errors.append("live profile tradable_balance_ratio is invalid")
    else:
        if not math.isfinite(tradable_balance_ratio) or tradable_balance_ratio > 0.10:
            errors.append("live profile must cap tradable_balance_ratio at 0.10")
    order_types = profile.get("order_types")
    if not isinstance(order_types, dict) or order_types.get("stoploss_on_exchange") is not True:
        errors.append("live profile must enable stoploss_on_exchange")

    required = ("approved_at", "owner", "strategy_revision", "strategy_source_sha256", "quant_report_sha256", "paper_run_end")
    if approval.get("acknowledgement") != "LIMITED_LIVE_APPROVED":
        errors.append("approval acknowledgement is missing")
    for field in required:
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            errors.append(f"approval field {field} is missing")
    report_hash = str(approval.get("quant_report_sha256", "")).lower()
    if len(report_hash) != 64 or any(character not in "0123456789abcdef" for character in report_hash):
        errors.append("approval quant_report_sha256 must be a SHA-256 hex digest")
    if quant_report_path is None or not quant_report_path.is_file():
        errors.append("passed quant gate report is missing")
    else:
        try:
            report_bytes = quant_report_path.read_bytes()
            quant_report = json.loads(report_bytes)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"passed quant gate report is invalid: {exc}")
        else:
            if not isinstance(quant_report, dict) or quant_report.get("passes") is not True:
                errors.append("quant gate report does not pass")
            if hashlib.sha256(report_bytes).hexdigest() != report_hash:
                errors.append("quant gate report SHA-256 does not match approval")
    strategy_hash = str(approval.get("strategy_source_sha256", "")).lower()
    if len(strategy_hash) != 64 or any(character not in "0123456789abcdef" for character in strategy_hash):
        errors.append("approval strategy_source_sha256 must be a SHA-256 hex digest")
    if strategy_source_path is None or not strategy_source_path.is_file():
        errors.append("active strategy source file is missing")
    elif hashlib.sha256(strategy_source_path.read_bytes()).hexdigest() != strategy_hash:
        errors.append("active strategy source SHA-256 does not match approval")

    try:
        clock_drift = float(clock_drift_fetcher())
    except (TypeError, ValueError, OSError) as exc:
        errors.append(f"could not verify Binance server time: {exc}")
    else:
        if not math.isfinite(clock_drift) or clock_drift < 0:
            errors.append("Binance clock drift is invalid")
        elif clock_drift > MAX_CLOCK_DRIFT_SECONDS:
            errors.append(
                f"host clock drift versus Binance is {clock_drift:.3f} seconds; synchronize the host clock before live release"
            )
    return errors


def main() -> None:
    if len(sys.argv) != 5:
        fail("profile path, approval-record path, passed quant-report path, and active strategy source path are required")
    profile = load_json(Path(sys.argv[1]), "live profile")
    approval = load_json(Path(sys.argv[2]), "live approval record")

    errors = validation_errors(profile, approval, Path(sys.argv[3]), Path(sys.argv[4]))
    if errors:
        fail(" ".join(errors))


if __name__ == "__main__":
    main()
