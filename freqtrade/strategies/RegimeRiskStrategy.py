from __future__ import annotations

from datetime import datetime

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_absolute
from trading_core.risk import RiskSettings, calculate_position_size


class RegimeRiskStrategy(IStrategy):
    """Long-only 1H strategy gated by a 4H bull-market regime."""

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    startup_candle_count = 220
    process_only_new_candles = True
    use_custom_stoploss = True
    position_adjustment_enable = True
    stoploss = -0.20
    minimal_roi = {"0": 10.0}
    use_exit_signal = True
    risk = RiskSettings()

    @property
    def protections(self) -> list[dict]:
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 6,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 24,
                "trade_limit": 1,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.03,
                "calculation_mode": "equity",
            },
        ]

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["macdhist"] = ta.MACD(dataframe)["macdhist"]
        dataframe["volume_sma"] = dataframe["volume"].rolling(20).mean()
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema50_4h"] > dataframe["ema200_4h"])
            & (dataframe["adx_4h"] > 20)
            & (dataframe["atr_pct_4h"] < 0.06)
            & (dataframe["ema20"] > dataframe["ema50"])
            & dataframe["rsi"].between(45, 65)
            & (dataframe["macdhist"] > 0)
            & (dataframe["macdhist"] >= dataframe["macdhist"].shift(1))
            & (dataframe["volume"] > dataframe["volume_sma"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "bull_regime_quant")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["ema20"] < dataframe["ema50"], "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float, proposed_stake: float, min_stake: float | None, max_stake: float, leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        stop = current_rate - (self.risk.atr_stop_multiple * float(dataframe.iloc[-1]["atr"]))
        return calculate_position_size(self.wallets.get_total_stake_amount(), current_rate, stop, self.risk, min_stake, max_stake)

    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:
        if order.ft_order_side != trade.entry_side:
            return
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade.set_custom_data("initial_risk_ratio", (self.risk.atr_stop_multiple * float(dataframe.iloc[-1]["atr"])) / order.safe_price)
        trade.set_custom_data("tp1_taken", False)

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, after_fill: bool, **kwargs) -> float | None:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        if not initial_risk:
            return None
        if current_profit >= initial_risk * self.risk.take_profit_one_r:
            return stoploss_from_absolute(trade.open_rate, current_rate=current_rate, is_short=False)
        return stoploss_from_absolute(trade.open_rate * (1 - initial_risk), current_rate=current_rate, is_short=False)

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, min_stake: float | None, max_stake: float, current_entry_rate: float, current_exit_rate: float, current_entry_profit: float, current_exit_profit: float, **kwargs) -> tuple[float | None, str | None]:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        if initial_risk and not trade.get_custom_data("tp1_taken", default=False) and current_profit >= initial_risk * self.risk.take_profit_one_r:
            trade.set_custom_data("tp1_taken", True)
            return (-trade.stake_amount / 2, "take_profit_1")
        return (None, None)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> str | None:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        return "take_profit_2" if initial_risk and current_profit >= initial_risk * self.risk.take_profit_two_r else None
