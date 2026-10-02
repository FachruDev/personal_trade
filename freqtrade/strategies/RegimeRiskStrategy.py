from __future__ import annotations

from datetime import datetime
import json
import logging
import math
import os

import requests
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, informative, stoploss_from_absolute
from trading_core.risk import RiskSettings, calculate_position_size
from trading_core.strategy import EntrySnapshot, Signal, classify_regime, evaluate_entry


logger = logging.getLogger(__name__)


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

    def _send_audit_event(self, event_type: str, **payload) -> None:
        """Emit best-effort audit data without affecting trade execution."""
        try:
            self.dp.send_msg(json.dumps({"event_type": event_type, **payload}, default=str))
        except Exception:
            logger.warning("Unable to send audit event '%s'.", event_type, exc_info=True)

    @staticmethod
    def _context_shadow() -> dict[str, object]:
        """Read advisory context for audit only; it never gates an order."""
        url = os.getenv("CONTEXT_FUSION_URL", "http://api:8000/v1/context/fusion")
        try:
            response = requests.get(url, timeout=1)
            response.raise_for_status()
            payload = response.json()
            recommendation_payload = payload.get("recommendation")
            if not isinstance(recommendation_payload, dict):
                raise ValueError("invalid context fusion response")
            recommendation = recommendation_payload.get("decision")
            multiplier = recommendation_payload.get("risk_multiplier")
            if not isinstance(recommendation, str) or not isinstance(multiplier, (int, float)):
                raise ValueError("invalid context fusion recommendation")
            return {
                "available": True,
                "recommendation": recommendation,
                "risk_multiplier": round(float(multiplier), 4),
            }
        except (requests.RequestException, ValueError, TypeError):
            return {"available": False}

    @staticmethod
    def _number(row, field: str) -> float | None:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def _audit_latest_decision(self, pair: str) -> None:
        if not hasattr(self, "_audited_candles"):
            self._audited_candles: dict[str, str] = {}
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return
        row = dataframe.iloc[-1]
        candle_at = str(row.get("date", "unknown"))
        if self._audited_candles.get(pair) == candle_at:
            return
        self._audited_candles[pair] = candle_at

        fields = ("close_4h", "ema50_4h", "ema200_4h", "adx_4h", "atr_pct_4h", "ema20", "ema50", "rsi", "macdhist", "volume", "volume_sma", "atr")
        values = {field: self._number(row, field) for field in fields}
        if any(value is None for value in values.values()):
            self._send_audit_event("hold", pair=pair, candle_at=candle_at, reason="indicator_data_unavailable")
            return

        regime = classify_regime(
            close=values["close_4h"],
            ema50=values["ema50_4h"],
            ema200=values["ema200_4h"],
            adx=values["adx_4h"],
            atr_percent=values["atr_pct_4h"],
            trend_adx_threshold=20,
        )
        previous_macd = self._number(dataframe.iloc[-2], "macdhist") if len(dataframe.index) > 1 else None
        if previous_macd is None:
            self._send_audit_event("hold", pair=pair, candle_at=candle_at, reason="previous_macd_unavailable")
            return
        snapshot = EntrySnapshot(
            ema20=values["ema20"],
            ema50=values["ema50"],
            rsi=values["rsi"],
            macd_histogram=values["macdhist"],
            previous_macd_histogram=previous_macd,
            volume=values["volume"],
            volume_sma=values["volume_sma"],
        )
        signal = evaluate_entry(regime, snapshot)
        details = {
            "pair": pair,
            "candle_at": candle_at,
            "regime": regime.value,
            "close": round(values["close_4h"], 8),
            "rsi": round(values["rsi"], 4),
            "atr": round(values["atr"], 8),
            "adx_4h": round(values["adx_4h"], 4),
        }
        if signal is Signal.BUY:
            self._send_audit_event(
                "quant_candidate",
                **details,
                enter_tag="bull_regime_quant",
                context_shadow=self._context_shadow(),
            )
            return

        failed_conditions = []
        if regime.value != "bull":
            failed_conditions.append(f"regime_{regime.value}")
        if not snapshot.ema20 > snapshot.ema50:
            failed_conditions.append("ema20_not_above_ema50")
        if not 45 <= snapshot.rsi <= 65:
            failed_conditions.append("rsi_outside_range")
        if not snapshot.macd_histogram > 0:
            failed_conditions.append("macd_not_bullish")
        if not snapshot.macd_histogram >= snapshot.previous_macd_histogram:
            failed_conditions.append("macd_not_improving")
        if not snapshot.volume > snapshot.volume_sma:
            failed_conditions.append("volume_below_average")
        self._send_audit_event("hold", **details, failed_conditions=failed_conditions)

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        if self.dp.runmode.value not in {"dry_run", "live"}:
            return
        for pair in self.dp.current_whitelist():
            try:
                self._audit_latest_decision(pair)
            except Exception:
                logger.warning("Unable to audit latest decision for %s.", pair, exc_info=True)

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """Fail closed when the operator kill-switch cannot be cleared."""
        url = os.getenv("BOT_KILL_SWITCH_URL", "http://api:8000/internal/kill-switch")
        try:
            response = requests.get(url, timeout=1)
            response.raise_for_status()
            if not bool(response.json().get("enabled")):
                return True
            reason = "kill_switch_enabled"
        except (requests.RequestException, ValueError, TypeError):
            reason = "kill_switch_state_unavailable"
        self._send_audit_event("risk_rejected", pair=pair, entry_rate=round(rate, 8), entry_tag=entry_tag, reason=reason)
        return False

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
        atr = float(dataframe.iloc[-1]["atr"])
        stop = current_rate - (self.risk.atr_stop_multiple * atr)
        wallet_balance = self.wallets.get_total_stake_amount()
        stake = calculate_position_size(wallet_balance, current_rate, stop, self.risk, min_stake, max_stake)
        risk_payload = {
            "pair": pair,
            "entry_rate": round(current_rate, 8),
            "stop_rate": round(stop, 8),
            "stake_amount": round(stake, 8),
            "risk_per_trade": self.risk.risk_per_trade,
            "entry_tag": entry_tag,
        }
        if stake <= 0:
            self._send_audit_event("risk_rejected", **risk_payload, reason="invalid_or_below_minimum_stake")
            return stake
        self._send_audit_event("risk_approved", **risk_payload)
        return stake

    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:
        if order.ft_order_side != trade.entry_side:
            return
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        initial_risk_ratio = (self.risk.atr_stop_multiple * float(dataframe.iloc[-1]["atr"])) / order.safe_price
        trade.set_custom_data("initial_risk_ratio", initial_risk_ratio)
        trade.set_custom_data("tp1_taken", False)
        self._send_audit_event("risk_attached_to_trade", pair=pair, trade_id=trade.id, initial_risk_ratio=round(initial_risk_ratio, 8))

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, after_fill: bool, **kwargs) -> float | None:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        if not initial_risk:
            return None
        if current_profit >= initial_risk * self.risk.take_profit_one_r:
            trailing_rate = max(trade.open_rate, current_rate * (1 - initial_risk))
            if not trade.get_custom_data("trailing_stop_logged", default=False):
                trade.set_custom_data("trailing_stop_logged", True)
                self._send_audit_event(
                    "trailing_stop_started",
                    pair=pair,
                    trade_id=trade.id,
                    current_profit=round(current_profit, 8),
                    trailing_rate=round(trailing_rate, 8),
                )
            return stoploss_from_absolute(trailing_rate, current_rate=current_rate, is_short=False)
        return stoploss_from_absolute(trade.open_rate * (1 - initial_risk), current_rate=current_rate, is_short=False)

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, min_stake: float | None, max_stake: float, current_entry_rate: float, current_exit_rate: float, current_entry_profit: float, current_exit_profit: float, **kwargs) -> tuple[float | None, str | None]:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        if initial_risk and not trade.get_custom_data("tp1_taken", default=False) and current_profit >= initial_risk * self.risk.take_profit_one_r:
            trade.set_custom_data("tp1_taken", True)
            self._send_audit_event("take_profit_1_requested", pair=trade.pair, trade_id=trade.id, current_profit=round(current_profit, 8))
            return (-trade.stake_amount / 2, "take_profit_1")
        return (None, None)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> str | None:
        initial_risk = trade.get_custom_data("initial_risk_ratio", default=None)
        if initial_risk and current_profit >= initial_risk * self.risk.take_profit_two_r:
            if not trade.get_custom_data("tp2_logged", default=False):
                trade.set_custom_data("tp2_logged", True)
                self._send_audit_event("take_profit_2_requested", pair=pair, trade_id=trade.id, current_profit=round(current_profit, 8))
            return "take_profit_2"
        return None


class LimitedRiskRegimeRiskStrategy(RegimeRiskStrategy):
    """Static low-risk variant used by paper and limited-live profiles."""

    risk = RiskSettings(
        risk_per_trade=0.0025,
        max_risk_per_trade=0.0025,
        max_open_trades=1,
        max_portfolio_risk=0.0025,
        daily_loss_limit=0.01,
    )
