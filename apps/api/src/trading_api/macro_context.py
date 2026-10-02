from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


FRED_SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "treasury_2y": "GS2",
    "treasury_10y": "GS10",
}


@dataclass(frozen=True)
class MacroContext:
    observed_at: datetime
    series: dict[str, dict[str, float | str | None]]

    def as_dict(self) -> dict:
        return {
            "observed_at": self.observed_at.isoformat(),
            "series": self.series,
            "mode": "shadow",
        }


async def latest_observation(client: httpx.AsyncClient, base_url: str, api_key: str, series_id: str) -> tuple[str, dict[str, float | str | None]]:
    response = await client.get(
        f"{base_url.rstrip('/')}/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10,
        },
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    latest = next((item for item in observations if item.get("value") not in {None, "."}), None)
    if latest is None:
        return series_id, {"value": None, "date": None}
    try:
        value: float | None = float(latest["value"])
    except (TypeError, ValueError):
        value = None
    return series_id, {"value": value, "date": latest.get("date")}


async def fetch_macro_context(base_url: str, api_key: str) -> MacroContext:
    async with httpx.AsyncClient(timeout=15) as client:
        values = await asyncio.gather(
            *(latest_observation(client, base_url, api_key, series_id) for series_id in FRED_SERIES.values())
        )
    by_series_id = dict(values)
    return MacroContext(
        observed_at=datetime.now(timezone.utc),
        series={name: by_series_id[series_id] for name, series_id in FRED_SERIES.items()},
    )
