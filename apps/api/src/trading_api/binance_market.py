from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from math import isfinite

import httpx


WATCHED_SYMBOLS = ("BTCUSDT", "ETHUSDT")


@dataclass(frozen=True)
class OrderBookContext:
    observed_at: datetime
    pairs: dict[str, dict[str, float | int | None]]

    def as_dict(self) -> dict:
        return {
            "observed_at": self.observed_at.isoformat(),
            "pairs": self.pairs,
            "mode": "shadow",
        }


def positive_number(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) and parsed > 0 else None


def orderbook_metrics(snapshot: dict, levels: int = 10) -> dict[str, float | int | None]:
    bids = snapshot.get("bids")
    asks = snapshot.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list):
        raise ValueError("Order book is missing bid or ask levels")

    def normalized_notional(rows: list) -> tuple[float, float | None, int]:
        total = 0.0
        first_price: float | None = None
        valid_levels = 0
        for row in rows[:levels]:
            if not isinstance(row, list) or len(row) < 2:
                continue
            price = positive_number(row[0])
            amount = positive_number(row[1])
            if price is None or amount is None:
                continue
            if first_price is None:
                first_price = price
            total += price * amount
            valid_levels += 1
        return total, first_price, valid_levels

    bid_notional, best_bid, bid_levels = normalized_notional(bids)
    ask_notional, best_ask, ask_levels = normalized_notional(asks)
    if best_bid is None or best_ask is None:
        raise ValueError("Order book has no valid best bid and ask")
    total_notional = bid_notional + ask_notional
    mid = (best_bid + best_ask) / 2
    return {
        "mid_price": mid,
        "bid_notional_top_levels": bid_notional,
        "ask_notional_top_levels": ask_notional,
        "imbalance": (bid_notional - ask_notional) / total_notional if total_notional else None,
        "spread_bps": ((best_ask - best_bid) / mid) * 10_000 if mid else None,
        "bid_levels": bid_levels,
        "ask_levels": ask_levels,
    }


async def fetch_market_connectivity(base_url: str) -> dict:
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/api/v3/exchangeInfo",
            params={"symbols": json.dumps(WATCHED_SYMBOLS, separators=(",", ":"))},
        )
        response.raise_for_status()
    symbols = {
        str(item.get("symbol")): str(item.get("status"))
        for item in response.json().get("symbols", [])
        if isinstance(item, dict)
    }
    pairs = {symbol: symbols.get(symbol, "MISSING") for symbol in WATCHED_SYMBOLS}
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "reachable": all(status == "TRADING" for status in pairs.values()),
        "pairs": pairs,
    }


async def fetch_orderbook_context(base_url: str) -> OrderBookContext:
    async with httpx.AsyncClient(timeout=8) as client:
        payloads: dict[str, dict] = {}
        for symbol in WATCHED_SYMBOLS:
            response = await client.get(
                f"{base_url.rstrip('/')}/api/v3/depth",
                params={"symbol": symbol, "limit": 20},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Order book provider returned an invalid payload")
            payloads[symbol] = payload
    return OrderBookContext(
        observed_at=datetime.now(timezone.utc),
        pairs={symbol: orderbook_metrics(payload) for symbol, payload in payloads.items()},
    )
