from __future__ import annotations

from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy


class PullbackTrendStrategy(RegimeRiskStrategy):
    """Research-only 1H pullback entry inside an established 4H uptrend.

    This tests a different hypothesis from the production momentum entry: buy
    a controlled pullback only after momentum begins to recover, while price
    remains above the 1H medium-term trend.
    """

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & (dataframe["adx_4h"] > 20)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["close"] <= dataframe["ema20"])
            & dataframe["rsi"].between(35, 50)
            & (dataframe["macdhist"] > dataframe["macdhist"].shift(1))
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "bull_regime_pullback")
        return dataframe
