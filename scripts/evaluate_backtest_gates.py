"""Evaluate frozen Freqtrade backtest artifacts against the release gate.

This intentionally does not optimize parameters or select a winner. It reads
three already-produced zip artifacts and gives a reproducible pass/fail result
for development, validation, and out-of-sample periods.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from zipfile import ZipFile


@dataclass(frozen=True)
class PeriodMetrics:
    name: str
    trades: int
    profit_total_pct: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    passes: bool
    failures: list[str]


def read_strategy_summary(artifact: Path) -> dict:
    with ZipFile(artifact) as archive:
        result_file = next(
            (
                item
                for item in archive.namelist()
                if item.endswith(".json") and not item.endswith("_config.json")
            ),
            None,
        )
        if result_file is None:
            raise ValueError(f"No Freqtrade result JSON found in {artifact}")
        result = json.loads(archive.read(result_file))
    strategies = result.get("strategy", {})
    if len(strategies) != 1:
        raise ValueError(f"Expected exactly one strategy in {artifact}")
    return next(iter(strategies.values()))


def evaluate_period(name: str, artifact: Path, min_trades: int, min_profit_factor: float, max_drawdown: float) -> PeriodMetrics:
    summary = read_strategy_summary(artifact)
    trades = int(summary["total_trades"])
    profit_factor = float(summary["profit_factor"])
    expectancy = float(summary["expectancy"])
    drawdown = float(summary["max_drawdown_account"])
    failures: list[str] = []
    if trades < min_trades:
        failures.append(f"trades {trades} < required {min_trades}")
    if profit_factor < min_profit_factor:
        failures.append(f"profit factor {profit_factor:.2f} < required {min_profit_factor:.2f}")
    if expectancy <= 0:
        failures.append(f"expectancy {expectancy:.4f} is not positive")
    if drawdown > max_drawdown:
        failures.append(f"drawdown {drawdown * 100:.2f}% > maximum {max_drawdown * 100:.2f}%")
    return PeriodMetrics(
        name=name,
        trades=trades,
        profit_total_pct=float(summary["profit_total"]) * 100,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown_pct=drawdown * 100,
        passes=not failures,
        failures=failures,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate three frozen Freqtrade backtest artifacts.")
    parser.add_argument("--label", required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out-of-sample", dest="out_of_sample", type=Path, required=True)
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--min-profit-factor", type=float, default=1.15)
    parser.add_argument("--max-drawdown", type=float, default=0.05)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    periods = [
        evaluate_period("development", args.development, args.min_trades, args.min_profit_factor, args.max_drawdown),
        evaluate_period("validation", args.validation, args.min_trades, args.min_profit_factor, args.max_drawdown),
        evaluate_period("out_of_sample", args.out_of_sample, args.min_trades, args.min_profit_factor, args.max_drawdown),
    ]
    report = {
        "label": args.label,
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
