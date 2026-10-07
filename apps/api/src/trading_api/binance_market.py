from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from math import isfinite

import httpx


WATCHED_SYMBOLS = ("BTCUSDT", "ETHUSDT")
CHART_INTERVALS = ("1h",)


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


def clock_drift_seconds(server_time_ms: object, observed_at: datetime) -> float:
    """Return the absolute local-vs-Binance clock difference at observation time."""
    server_time = positive_number(server_time_ms)
    if server_time is None:
        raise ValueError("Binance server time is missing or invalid")
    return abs(observed_at.timestamp() - (server_time / 1_000))


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
        response, time_response = await asyncio.gather(
            client.get(
                f"{base_url.rstrip('/')}/api/v3/exchangeInfo",
                params={"symbols": json.dumps(WATCHED_SYMBOLS, separators=(",", ":"))},
            ),
            client.get(f"{base_url.rstrip('/')}/api/v3/time"),
        )
        response.raise_for_status()
        time_response.raise_for_status()
    symbols = {
        str(item.get("symbol")): str(item.get("status"))
        for item in response.json().get("symbols", [])
        if isinstance(item, dict)
    }
    pairs = {symbol: symbols.get(symbol, "MISSING") for symbol in WATCHED_SYMBOLS}
    observed_at = datetime.now(timezone.utc)
    drift_seconds = clock_drift_seconds(time_response.json().get("serverTime"), observed_at)
    return {
        "observed_at": observed_at.isoformat(),
        "reachable": all(status == "TRADING" for status in pairs.values()),
        "pairs": pairs,
        "clock_drift_seconds": round(drift_seconds, 3),
        "clock_synchronized": drift_seconds <= 2.0,
    }


async def fetch_market_candles(base_url: str, symbol: str, interval: str = "1h", limit: int = 48) -> dict:
    """Return a small, public candle series for the personal dashboard.

    This deliberately uses Binance's public endpoint: it neither reads the
    account nor participates in strategy or execution decisions.
    """
    if symbol not in WATCHED_SYMBOLS:
        raise ValueError("Symbol is outside the dashboard watchlist")
    if interval not in CHART_INTERVALS:
        raise ValueError("Unsupported chart interval")
    if not 12 <= limit <= 168:
        raise ValueError("Chart limit must be between 12 and 168")

    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Candle provider returned an invalid payload")

    candles: list[dict[str, float | int]] = []
    for item in payload:
        if not isinstance(item, list) or len(item) < 6:
            raise ValueError("Candle provider returned an invalid candle")
        opened_at = positive_number(item[0])
        open_price = positive_number(item[1])
        high = positive_number(item[2])
        low = positive_number(item[3])
        close = positive_number(item[4])
        volume = positive_number(item[5])
        if None in (opened_at, open_price, high, low, close, volume):
            raise ValueError("Candle provider returned a malformed candle")
        candles.append(
            {
                "opened_at": int(opened_at),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return {
        "symbol": symbol,
        "interval": interval,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "candles": candles,
        "mode": "public_market_data",
        "execution_effect": "none",
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
