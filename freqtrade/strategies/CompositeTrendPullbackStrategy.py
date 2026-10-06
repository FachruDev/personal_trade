"""Pre-registered BTC/ETH trend-pullback research hypothesis.

This strategy is intentionally not referenced by a paper or live profile. It
inherits only the already-tested ATR exits and risk callbacks; its entry logic
is evaluated independently through the experiment script.
"""

from __future__ import annotations

import math
import os

import requests
from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy
from freqtrade.strategy import informative
from trading_core.composite import CompositeScoreInput, score_composite_pullback


class CompositeTrendPullbackStrategy(RegimeRiskStrategy):
    """4H bull trend with a measured 1H pullback and recovery confirmation."""

    atr_percentile_window = 540  # 90 days of 4H candles.
    # 540 informative 4H candles require 2,160 1H candles, plus a buffer.
    startup_candle_count = 2200
    atr_normal_lower_quantile = 0.20
    atr_normal_upper_quantile = 0.80
    pullback_tolerance_atr = 0.30
    maximum_extension_atr = 1.00
    volume_multiple = 1.10

    @staticmethod
    def _finite(value: object) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators_4h(dataframe, metadata)
        # Shift excludes the current bar from its own percentile boundaries.
        history = dataframe["atr_pct"].rolling(self.atr_percentile_window, min_periods=self.atr_percentile_window)
        dataframe["atr_pct_normal_low"] = history.quantile(self.atr_normal_lower_quantile).shift(1)
        dataframe["atr_pct_normal_high"] = history.quantile(self.atr_normal_upper_quantile).shift(1)
        return dataframe

    @classmethod
    def entry_conditions(cls, dataframe: DataFrame) -> DataFrame:
        volatility_normal = (
            (dataframe["atr_pct_4h"] >= dataframe["atr_pct_normal_low_4h"])
            & (dataframe["atr_pct_4h"] <= dataframe["atr_pct_normal_high_4h"])
        )
        pullback_touch = (dataframe["low"] - dataframe["ema20"]).abs() <= dataframe["atr"] * cls.pullback_tolerance_atr
        structure = (
            (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["ema50"])
            & pullback_touch
            & (dataframe["close"] >= dataframe["ema20"])
            & ((dataframe["close"] - dataframe["ema20"]) <= dataframe["atr"] * cls.maximum_extension_atr)
        )
        rsi_recovering = dataframe["rsi"].between(40, 55) & (dataframe["rsi"] > dataframe["rsi"].shift(1))
        macd_improving = dataframe["macdhist"] > dataframe["macdhist"].shift(1)
        volume_confirmed = dataframe["volume"] >= dataframe["volume_sma"] * cls.volume_multiple
        bullish_regime = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & (dataframe["adx_4h"] > 20)
        )
        return DataFrame(
            {
                "bullish_regime": bullish_regime,
                "volatility_normal": volatility_normal,
                "pullback_structure": structure,
                "rsi_recovering": rsi_recovering,
                "macd_improving": macd_improving,
                "volume_confirmed": volume_confirmed,
            },
            index=dataframe.index,
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = self.entry_conditions(dataframe)
        entry_allowed = conditions.all(axis=1)
        dataframe.loc[entry_allowed, "enter_long"] = 1
        dataframe.loc[entry_allowed, "enter_tag"] = "composite_trend_pullback"
        return dataframe

    @staticmethod
    def _context_shadow() -> dict[str, object]:
        """Capture advisory data only after a research candidate is found."""
        url = os.getenv("CONTEXT_SHADOW_SNAPSHOT_URL", "http://api:8000/v1/context/shadow-snapshot")
        try:
            response = requests.get(url, timeout=1)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("mode") != "shadow":
                raise ValueError("invalid context shadow snapshot")
            return payload
        except (requests.RequestException, ValueError, TypeError):
            return {"available": False, "mode": "shadow"}

    def _audit_latest_decision(self, pair: str) -> None:
        """Add score and advisory context to research candidates only."""
        if not hasattr(self, "_audited_candles"):
            self._audited_candles: dict[str, str] = {}
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe.index) < 2:
            return
        row = dataframe.iloc[-1]
        candle_at = str(row.get("date", "unknown"))
        if self._audited_candles.get(pair) == candle_at:
            return
        self._audited_candles[pair] = candle_at
        required = ("close", "ema20", "ema50", "rsi", "macdhist", "volume", "volume_sma", "atr", "close_4h", "ema50_4h", "ema200_4h", "adx_4h", "atr_pct_4h", "atr_pct_normal_low_4h", "atr_pct_normal_high_4h")
        if any(not self._finite(row.get(field)) for field in required):
            self._send_audit_event("hold", pair=pair, candle_at=candle_at, strategy="composite_trend_pullback", reason="indicator_data_unavailable")
            return
        conditions = self.entry_conditions(dataframe).iloc[-1]
        score = score_composite_pullback(
            CompositeScoreInput(**{key: bool(conditions[key]) for key in conditions.index}),
            entry_allowed=bool(conditions.all()),
        )
        details = {
            "pair": pair,
            "candle_at": candle_at,
            "strategy": "composite_trend_pullback",
            "score": score.total,
            "score_components": score.components,
            "decision": score.decision.value,
            "conditions": {key: bool(conditions[key]) for key in conditions.index},
        }
        if score.decision.value == "ENTRY_CANDIDATE":
            self._send_audit_event("quant_candidate", **details, context_shadow=self._context_shadow())
        else:
            self._send_audit_event("hold", **details)
