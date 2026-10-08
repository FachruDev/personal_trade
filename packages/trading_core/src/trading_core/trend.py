from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import stdev
from typing import Sequence


@dataclass(frozen=True)
class TrendSettings:
    """Daily long-or-cash trend exposure with volatility targeting (spot, no leverage)."""

    lookbacks: tuple[int, ...] = (50, 100, 150)
    target_volatility: float = 0.40
    volatility_window: int = 20
    rebalance_band: float = 0.10
    periods_per_year: int = 365


def trend_score(closes: Sequence[float], lookbacks: Sequence[int]) -> float:
    """Fraction of simple moving averages that sit below the latest close.

    Returns 0.0 until the longest lookback has a full window, so a pair with short
    history never receives exposure.
    """
    if not lookbacks or len(closes) < max(lookbacks):
        return 0.0
    last = closes[-1]
    above = sum(1 for n in lookbacks if last > sum(closes[-n:]) / n)
    return above / len(lookbacks)


def volatility_scale(closes: Sequence[float], target: float, window: int, periods_per_year: int = 365) -> float:
    """Exposure multiplier in [0, 1]: target volatility over realised volatility, capped at 1.

    The cap keeps the strategy unlevered. Returns 0.0 while history is insufficient.
    """
    if window < 2 or len(closes) < window + 1:
        return 0.0
    tail = closes[-(window + 1):]
    if any(price <= 0 for price in tail):
        return 0.0
    returns = [tail[i] / tail[i - 1] - 1 for i in range(1, len(tail))]
    realised = stdev(returns) * sqrt(periods_per_year)
    return 1.0 if realised <= 0 else min(1.0, target / realised)


def target_exposure(closes: Sequence[float], settings: TrendSettings = TrendSettings()) -> float:
    """Desired fraction of this pair's capital budget to hold, in [0, 1]."""
    score = trend_score(closes, settings.lookbacks)
    if score <= 0:
        return 0.0
    return score * volatility_scale(closes, settings.target_volatility, settings.volatility_window, settings.periods_per_year)


def rebalanced_exposure(current: float, target: float, band: float) -> float:
    """Dead-band rule used in research: ignore small target changes to save fees.

    Always move when exiting to zero, or when entering from zero above half the band.
    """
    if abs(target - current) > band:
        return target
    if target == 0 and current != 0:
        return 0.0
    if current == 0 and target > band / 2:
        return target
    return current
