"""Public, read-only metadata for pre-declared strategy experiments."""

from __future__ import annotations


COMPOSITE_TREND_PULLBACK = {
    "label": "composite_trend_pullback",
    "strategy": "CompositeTrendPullbackStrategy",
    "status": "rejected",
    "mode": "research_only",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "timeframes": {"entry": "1h", "trend": "4h"},
    "hypothesis": "A 4H bull trend plus a measured 1H EMA20 pullback, recovery momentum, normal volatility, and above-average volume can improve entry quality.",
    "entry_summary": [
        "4H close above EMA200, EMA50 above EMA200, ADX above 20",
        "4H ATR% within the previous 90-day 20th–80th percentile range",
        "1H EMA20 above EMA50, EMA20 touch within 0.3 ATR, and close no more than 1 ATR above EMA20",
        "1H RSI recovers in 40–55, MACD histogram improves, volume at least 1.1x 20-candle average",
    ],
    "risk_profile": {
        "research": "Existing ATR exit callbacks only; no production or paper profile change",
        "promotion": "0.25% risk per trade and one open paper position only after the complete gate passes",
    },
    "validation": {
        "periods": ["development", "validation", "out_of_sample"],
        "required_profit_factor": 1.15,
        "required_positive_expectancy": True,
        "required_trades_per_period": 30,
        "maximum_drawdown_percent": 5.0,
        "integrity_checks": ["lookahead", "recursive"],
        "result": {
            "passes": False,
            "development": {"trades": 3, "profit_factor": 1.22, "return_percent": 0.13, "maximum_drawdown_percent": 0.61},
            "validation": {"trades": 0, "profit_factor": 0.0, "return_percent": 0.0, "maximum_drawdown_percent": 0.0},
            "out_of_sample": {"trades": 0, "profit_factor": 0.0, "return_percent": 0.0, "maximum_drawdown_percent": 0.0},
            "reason": "The fixed entry conditions produce too few observations for validation or promotion.",
        },
    },
    "context_policy": "Global, macro, order-book, news, and AI data are captured as shadow metadata. They cannot alter entries, stake, stops, or exits.",
}

ORDERBOOK_IMBALANCE_SHADOW = {
    "label": "orderbook_imbalance_shadow",
    "strategy": "OrderBookImbalanceShadowResearch",
    "status": "collecting_data",
    "mode": "shadow_only",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "timeframes": {"entry": "5m snapshot", "trend": "60m / 240m forward"},
    "hypothesis": "The public top-ten-level bid/ask imbalance may be associated with forward returns, before it is considered as a separate strategy feature.",
    "entry_summary": [
        "Public Binance top-ten depth snapshots are collected every five minutes",
        "The fixed sample gate is four continuous weeks: 8,064 snapshots with at least 95% cadence coverage",
        "Only pre-declared bid-heavy, neutral, and ask-heavy imbalance buckets are evaluated",
        "Only 60-minute and 240-minute forward-return horizons are evaluated",
    ],
    "risk_profile": {
        "research": "No effect on orders, stake, stop-loss, take-profit, or exit behavior",
        "promotion": "Not eligible until collection is complete, evidence is stable, and a separate frozen strategy passes the complete quant gate",
    },
    "validation": {
        "periods": ["four_week_continuous_collection", "60_minute_forward_return", "240_minute_forward_return"],
        "required_profit_factor": 0.0,
        "required_positive_expectancy": False,
        "required_trades_per_period": 0,
        "maximum_drawdown_percent": 0.0,
        "integrity_checks": ["fixed_buckets", "fixed_horizons", "shadow_only"],
        "gate_description": "8,064 snapshot dengan cakupan cadence minimal 95%, lalu evaluasi forward return yang sudah ditetapkan. Ini belum merupakan strategi trade.",
    },
    "context_policy": "Order-book data remains audit-only. It cannot create, reject, resize, stop, or exit a Freqtrade position.",
}


def experiment_catalog() -> list[dict]:
    return [COMPOSITE_TREND_PULLBACK, ORDERBOOK_IMBALANCE_SHADOW]
