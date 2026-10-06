"""Deterministic scoring for the research-only composite pullback hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CompositeDecision(StrEnum):
    HOLD = "HOLD"
    WATCH = "WATCH"
    ENTRY_CANDIDATE = "ENTRY_CANDIDATE"


@dataclass(frozen=True)
class CompositeScoreInput:
    bullish_regime: bool
    rsi_recovering: bool
    macd_improving: bool
    volume_confirmed: bool
    volatility_normal: bool
    pullback_structure: bool


@dataclass(frozen=True)
class CompositeScore:
    total: float
    components: dict[str, float]
    decision: CompositeDecision


def score_composite_pullback(snapshot: CompositeScoreInput, entry_allowed: bool) -> CompositeScore:
    """Score a candidate for audit; ``entry_allowed`` remains the order gate.

    The fixed weights explain signal quality but deliberately do not create an
    order by themselves. This avoids silently substituting subjective score
    tuning for the deterministic strategy rules.
    """

    components = {
        "trend": 30.0 if snapshot.bullish_regime else 0.0,
        "momentum": (12.5 if snapshot.rsi_recovering else 0.0) + (12.5 if snapshot.macd_improving else 0.0),
        "volume": 20.0 if snapshot.volume_confirmed else 0.0,
        "volatility": 15.0 if snapshot.volatility_normal else 0.0,
        "structure": 10.0 if snapshot.pullback_structure else 0.0,
    }
    total = sum(components.values())
    if entry_allowed:
        decision = CompositeDecision.ENTRY_CANDIDATE
    elif snapshot.bullish_regime and total >= 50:
        decision = CompositeDecision.WATCH
    else:
        decision = CompositeDecision.HOLD
    return CompositeScore(total=total, components=components, decision=decision)
