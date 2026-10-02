from __future__ import annotations

from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy


class DonchianBreakoutStrategy(RegimeRiskStrategy):
    """Research-only 1H Donchian breakout inside a confirmed 4H uptrend.

    This intentionally removes the baseline EMA/RSI/MACD timing stack. Entries
    require a close above the prior 20 completed hourly highs; exits use the
    prior 10 completed hourly lows, while inherited ATR risk controls remain.
    """

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["donchian_entry_high"] = dataframe["high"].rolling(20).max().shift(1)
        dataframe["donchian_exit_low"] = dataframe["low"].rolling(10).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["close"] > dataframe["donchian_entry_high"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "donchian_breakout")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["donchian_exit_low"], "exit_long"] = 1
        return dataframe