from __future__ import annotations

from pandas import DataFrame

from RegimeRiskStrategy import RegimeRiskStrategy


class TrendContinuationStrategy(RegimeRiskStrategy):
    """Research-only continuation entry after a 1H trend-reclaim.

    The strategy removes the oscillator and volume-average filters. It tests
    whether a small number of 1H EMA 20 reclaims, inside a stronger 4H trend,
    is more robust than trying to time each local momentum pattern.
    """

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["close"].shift(1) <= dataframe["ema20"].shift(1))
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "bull_regime_ema_reclaim")
        return dataframe
