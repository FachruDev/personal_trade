from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass(frozen=True)
class GlobalMarketContext:
    observed_at: datetime
    regime: str
    market_cap_change_24h: float | None
    btc_dominance: float | None
    total_market_cap_usd: float | None
    total_volume_usd: float | None

    def as_dict(self) -> dict:
        return {
            "observed_at": self.observed_at.isoformat(),
            "regime": self.regime,
            "market_cap_change_24h": self.market_cap_change_24h,
            "btc_dominance": self.btc_dominance,
            "total_market_cap_usd": self.total_market_cap_usd,
            "total_volume_usd": self.total_volume_usd,
            "mode": "shadow",
        }


def number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def classify_global_regime(market_cap_change_24h: float | None) -> str:
    if market_cap_change_24h is None:
        return "UNKNOWN"
    if market_cap_change_24h <= -3:
        return "RISK_OFF"
    if market_cap_change_24h >= 1:
        return "RISK_ON"
    return "NEUTRAL"


async def fetch_global_market_context(base_url: str, api_key: str | None) -> GlobalMarketContext:
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{base_url.rstrip('/')}/global", headers=headers)
        response.raise_for_status()
    data = response.json().get("data", {})
    change = number(data.get("market_cap_change_percentage_24h_usd"))
    dominance = data.get("market_cap_percentage", {})
    market_cap = data.get("total_market_cap", {})
    volume = data.get("total_volume", {})
    return GlobalMarketContext(
        observed_at=datetime.now(timezone.utc),
        regime=classify_global_regime(change),
        market_cap_change_24h=change,
        btc_dominance=number(dominance.get("btc")),
        total_market_cap_usd=number(market_cap.get("usd")),
        total_volume_usd=number(volume.get("usd")),
    )
