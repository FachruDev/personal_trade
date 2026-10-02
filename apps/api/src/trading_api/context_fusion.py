from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FusionDecision = Literal["NEUTRAL", "REDUCE_RISK", "HOLD"]


@dataclass(frozen=True)
class FusionRecommendation:
    decision: FusionDecision
    risk_multiplier: float
    reasons: list[str]
    mode: str = "shadow"

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "risk_multiplier": self.risk_multiplier,
            "reasons": self.reasons,
            "mode": self.mode,
        }


def number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def recommend_context_risk(global_context: dict | None, macro_context: dict | None, ai_assessment: dict | None) -> FusionRecommendation:
    reasons: list[str] = []
    global_regime = str((global_context or {}).get("regime", "UNKNOWN"))
    if global_regime == "RISK_OFF":
        reasons.append("global_market_risk_off")

    series = (macro_context or {}).get("series", {})
    two_year = number((series.get("treasury_2y") or {}).get("value")) if isinstance(series, dict) else None
    ten_year = number((series.get("treasury_10y") or {}).get("value")) if isinstance(series, dict) else None
    if two_year is not None and ten_year is not None and two_year - ten_year >= 0.25:
        reasons.append("macro_curve_inverted")

    bias = str((ai_assessment or {}).get("market_bias", "neutral")).lower()
    confidence = number((ai_assessment or {}).get("confidence")) or 0.0
    risk_level = str((ai_assessment or {}).get("risk_level", "low")).lower()
    if bias == "bearish" and confidence >= 0.70 and risk_level == "high":
        return FusionRecommendation("HOLD", 0.0, reasons + ["ai_high_confidence_bearish"])
    if bias == "bearish" and confidence >= 0.65:
        reasons.append("ai_bearish")

    if reasons:
        return FusionRecommendation("REDUCE_RISK", 0.5, reasons)
    return FusionRecommendation("NEUTRAL", 1.0, ["no_context_conflict"])
