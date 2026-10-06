"""Public, read-only metadata for pre-declared strategy experiments."""

from __future__ import annotations


COMPOSITE_TREND_PULLBACK = {
    "label": "composite_trend_pullback",
    "strategy": "CompositeTrendPullbackStrategy",
    "status": "rejected",
    "mode": "research_only",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "timeframes": {"entry": "1h", "trend": "4h"},
    "hypothesis": "Trend 4H bullish, pullback EMA20 pada 1H, pemulihan momentum, volatilitas normal, dan volume di atas rata-rata diuji untuk meningkatkan kualitas entry.",
    "entry_summary": [
        "4H: close di atas EMA200, EMA50 di atas EMA200, ADX di atas 20",
        "4H: ATR% berada pada rentang persentil 20–80 dari 90 hari sebelumnya",
        "1H: EMA20 di atas EMA50, low menyentuh EMA20 dalam 0,3 ATR, close maksimal 1 ATR di atas EMA20",
        "1H: RSI pulih pada area 40–55, histogram MACD membaik, volume minimal 1,1× rata-rata 20 candle",
    ],
    "risk_profile": {
        "research": "Hanya callback exit ATR yang ada; tidak ada perubahan profile paper atau production",
        "promotion": "Risiko 0,25% per trade dan satu posisi paper terbuka hanya setelah seluruh gate lolos",
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
            "reason": "Kondisi entry yang dikunci menghasilkan terlalu sedikit observasi untuk validasi atau promosi.",
        },
    },
    "context_policy": "Data global, macro, order-book, news, dan AI hanya dicatat sebagai metadata shadow. Data tersebut tidak dapat mengubah entry, ukuran posisi, stop, atau exit.",
}

ORDERBOOK_IMBALANCE_SHADOW = {
    "label": "orderbook_imbalance_shadow",
    "strategy": "OrderBookImbalanceShadowResearch",
    "status": "collecting_data",
    "mode": "shadow_only",
    "pairs": ["BTC/USDT", "ETH/USDT"],
    "timeframes": {"entry": "5m snapshot", "trend": "60m / 240m forward"},
    "hypothesis": "Imbalance bid/ask dari sepuluh level order-book publik diuji terhadap return ke depan sebelum dipertimbangkan sebagai fitur strategi terpisah.",
    "entry_summary": [
        "Snapshot depth Binance publik pada sepuluh level teratas dikumpulkan tiap lima menit",
        "Gate sampel dikunci pada empat minggu kontinu: 8.064 snapshot dengan cakupan cadence minimal 95%",
        "Hanya bucket imbalance bid-heavy, netral, dan ask-heavy yang sudah ditetapkan akan dievaluasi",
        "Hanya horizon return ke depan 60 dan 240 menit yang dievaluasi",
    ],
    "risk_profile": {
        "research": "Tidak memengaruhi order, ukuran posisi, stop-loss, take-profit, atau exit",
        "promotion": "Belum dapat dipromosikan sampai koleksi selesai, bukti stabil, dan strategi beku terpisah lolos seluruh quant gate",
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
    "context_policy": "Data order-book tetap audit-only. Data ini tidak dapat membuat, menolak, mengubah ukuran, menghentikan, atau menutup posisi Freqtrade.",
}


def experiment_catalog() -> list[dict]:
    return [COMPOSITE_TREND_PULLBACK, ORDERBOOK_IMBALANCE_SHADOW]
