from __future__ import annotations

import talib.abstract as ta
from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy


class TrendPullbackRecoveryStrategy(RegimeRiskStrategy):
    """Research-only recovery after a shallow pullback in a 4H uptrend.

    This is a pre-declared, separate hypothesis from the earlier MACD pullback:
    the entry requires an oversold stochastic crossover and an RSI recovery,
    rather than a positive MACD histogram. It keeps the inherited ATR risk and
    exit behavior so the experiment changes the entry family only.
    """

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        stochastic = ta.STOCH(dataframe, fastk_period=14, slowk_period=3, slowd_period=3)
        dataframe["stoch_k"] = stochastic["slowk"]
        dataframe["stoch_d"] = stochastic["slowd"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & dataframe["adx_4h"].between(15, 35)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["rsi"] > 40)
            & (dataframe["rsi"].shift(1) <= 40)
            & (dataframe["stoch_k"] > dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1))
            & (dataframe["stoch_k"] < 50)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "trend_pullback_recovery")
        return dataframe
