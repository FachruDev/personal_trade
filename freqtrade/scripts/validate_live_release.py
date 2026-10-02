"""Fail closed when Compose is configured for a limited-live release.

This is a startup gate, not evidence that the strategy is profitable. The
operator must still satisfy the full checklist and preserve the reviewed
approval record outside Git.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


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


def main() -> None:
    if len(sys.argv) != 3:
        fail("profile path and approval-record path are required")
    profile = load_json(Path(sys.argv[1]), "live profile")
    approval = load_json(Path(sys.argv[2]), "live approval record")

    if profile.get("dry_run") is not False:
        fail("live profile must explicitly set dry_run=false")
    if profile.get("max_open_trades") != 1:
        fail("live profile must allow exactly one open trade")
    if float(profile.get("tradable_balance_ratio", 1)) > 0.10:
        fail("live profile must cap tradable_balance_ratio at 0.10")
    order_types = profile.get("order_types")
    if not isinstance(order_types, dict) or order_types.get("stoploss_on_exchange") is not True:
        fail("live profile must enable stoploss_on_exchange")

    required = ("approved_at", "owner", "strategy_revision", "quant_report_sha256", "paper_run_end")
    if approval.get("acknowledgement") != "LIMITED_LIVE_APPROVED":
        fail("approval acknowledgement is missing")
    for field in required:
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            fail(f"approval field {field} is missing")
    report_hash = approval["quant_report_sha256"].lower()
    if len(report_hash) != 64 or any(character not in "0123456789abcdef" for character in report_hash):
        fail("approval quant_report_sha256 must be a SHA-256 hex digest")


if __name__ == "__main__":
    main()
