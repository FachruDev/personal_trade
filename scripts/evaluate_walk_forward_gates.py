"""Evaluate fixed rolling forward artifacts without tuning or selecting parameters."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from evaluate_backtest_gates import evaluate_period


def artifact_argument(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise argparse.ArgumentTypeError("Each --artifact must use name=path.zip")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate pre-registered rolling forward backtest artifacts.")
    parser.add_argument("--label", required=True)
    parser.add_argument("--artifact", action="append", type=artifact_argument, required=True)
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--min-profit-factor", type=float, default=1.15)
    parser.add_argument("--max-drawdown", type=float, default=0.05)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    artifacts: list[tuple[str, Path]] = args.artifact
    names = [name for name, _ in artifacts]
    if len(set(names)) != len(names):
        parser.error("Each forward fold name must be unique")

    periods = [
        evaluate_period(name, artifact, args.min_trades, args.min_profit_factor, args.max_drawdown)
        for name, artifact in artifacts
    ]
    report = {
        "label": args.label,
        "protocol": "fixed_parameter_rolling_forward",
        "gate": {
            "min_trades": args.min_trades,
            "min_profit_factor": args.min_profit_factor,
            "positive_expectancy_required": True,
            "max_drawdown_pct": args.max_drawdown * 100,
        },
        "passes": all(period.passes for period in periods),
        "periods": [asdict(period) for period in periods],
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
