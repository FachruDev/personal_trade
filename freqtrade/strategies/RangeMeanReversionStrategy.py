from __future__ import annotations

import talib.abstract as ta
from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy


class RangeMeanReversionStrategy(RegimeRiskStrategy):
    """Research-only mean-reversion entry in low-trend, non-bear 4H markets.

    This is intentionally a separate hypothesis from the rejected trend and
    breakout families: buy an hourly oversold deviation only when 4H price is
    above its long-term baseline and ADX does not show a strong downtrend.
    """


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        bands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] >= dataframe["ema200_4h"])
            & (dataframe["adx_4h"] < 20)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["rsi"] < 30)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "range_mean_reversion")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe["close"] >= dataframe["bb_middle"]) | (dataframe["rsi"] >= 55), "exit_long"] = 1
        return dataframe