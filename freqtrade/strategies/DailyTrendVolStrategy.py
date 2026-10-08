from __future__ import annotations

from datetime import datetime
import json
import logging
import math
import os

import requests
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from trading_core.trend import TrendSettings, rebalanced_exposure


logger = logging.getLogger(__name__)


class DailyTrendVolStrategy(IStrategy):
    """Long-or-cash daily trend ensemble with volatility targeting (spot, no leverage).

    Exposure per pair = share of candles above the 50/100/150-day SMAs, scaled down when
    20-day realised volatility exceeds the target. Each pair gets an equal capital budget.
    Entries and exits trade at the next daily open after the signal candle closes.
    """

    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    startup_candle_count = 200
    process_only_new_candles = True
    position_adjustment_enable = True
    use_exit_signal = True
    # Wide disaster stop only; the trend exit is the real risk control (see research/README.md).
    stoploss = -0.30
    minimal_roi = {"0": 100}
    trend = TrendSettings()
    pair_count = 2
    # Circuit breaker, as a share of the capital this strategy deploys (not of the whole account).
    drawdown_limit = 0.30
    drawdown_lookback_days = 365
    drawdown_pause_days = 30

    def _send_audit_event(self, event_type: str, **payload) -> None:
        """Emit best-effort audit data without affecting trade execution."""
        try:
            self.dp.send_msg(json.dumps({"event_type": event_type, **payload}, default=str))
        except Exception:
            logger.warning("Unable to send audit event '%s'.", event_type, exc_info=True)

    @staticmethod
    def _number(row, field: str) -> float | None:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def _latest_row(self, pair: str):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        return None if dataframe.empty else dataframe.iloc[-1]

    def _account_equity(self) -> float:
        """Free stake balance plus open positions at market value.

        Freqtrade's own `get_total_stake_amount` values open trades at cost, which understates
        equity while positions are in profit and would shrink the budget during a rally.
        """
        equity = self.wallets.get_free(self.config["stake_currency"])
        for open_trade in Trade.get_open_trades():
            row = self._latest_row(open_trade.pair)
            price = None if row is None else self._number(row, "close")
            equity += open_trade.amount * (price if price else open_trade.open_rate)
        return equity

    def _pair_budget(self) -> float:
        ratio = float(self.config.get("tradable_balance_ratio") or 1.0)
        return self._account_equity() * ratio / self.pair_count

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        if self.dp.runmode.value not in {"dry_run", "live"}:
            return
        if not hasattr(self, "_audited_candles"):
            self._audited_candles: dict[str, str] = {}
        for pair in self.dp.current_whitelist():
            try:
                row = self._latest_row(pair)
                if row is None:
                    continue
                candle_at = str(row.get("date", "unknown"))
                if self._audited_candles.get(pair) == candle_at:
                    continue
                self._audited_candles[pair] = candle_at
                self._send_audit_event(
                    "trend_target",
                    pair=pair,
                    candle_at=candle_at,
                    trend_score=self._number(row, "trend_score"),
                    vol_scale=self._number(row, "vol_scale"),
                    exposure=self._number(row, "exposure"),
                )
            except Exception:
                logger.warning("Unable to audit trend target for %s.", pair, exc_info=True)

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
        """Fail closed when the operator kill-switch cannot be cleared (dry-run and live only)."""
        if self.dp.runmode.value not in {"dry_run", "live"}:
            return True  # backtests have no operator and must not depend on the API service
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
        """Pause new entries after a drawdown of `drawdown_limit` of the deployed capital.

        Freqtrade measures this against the whole account using closed trades only, so the
        threshold is scaled by `tradable_balance_ratio`. Open positions keep following their
        own exit signal; the volatility target and the per-position stop limit open losses.
        """
        ratio = float(self.config.get("tradable_balance_ratio") or 1.0)
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": self.drawdown_lookback_days,
                "trade_limit": 2,
                "stop_duration_candles": self.drawdown_pause_days,
                "max_allowed_drawdown": round(self.drawdown_limit * ratio, 4),
                "calculation_mode": "equity",
            }
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        settings = self.trend
        close = dataframe["close"]
        above = None
        for lookback in settings.lookbacks:
            flag = (close > close.rolling(lookback).mean()).astype(float)
            above = flag if above is None else above + flag
        score = (above / len(settings.lookbacks)).where(close.rolling(max(settings.lookbacks)).mean().notna(), 0.0)
        realised = close.pct_change().rolling(settings.volatility_window).std() * math.sqrt(settings.periods_per_year)
        scale = (settings.target_volatility / realised).clip(upper=1.0).fillna(0.0)
        dataframe["trend_score"] = score
        dataframe["vol_scale"] = scale
        dataframe["exposure"] = score * scale
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (dataframe["exposure"] > self.trend.rebalance_band / 2) & (dataframe["volume"] > 0)
        dataframe.loc[conditions, ["enter_long", "enter_tag"]] = (1, "daily_trend")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["trend_score"] == 0, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float, proposed_stake: float, min_stake: float | None, max_stake: float, leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        row = self._latest_row(pair)
        exposure = None if row is None else self._number(row, "exposure")
        if exposure is None or exposure <= 0:
            self._send_audit_event("risk_rejected", pair=pair, entry_rate=round(current_rate, 8), entry_tag=entry_tag, reason="no_trend_exposure")
            return 0.0
        stake = min(self._pair_budget() * exposure, max_stake)
        if min_stake is not None and stake < min_stake:
            self._send_audit_event("risk_rejected", pair=pair, entry_rate=round(current_rate, 8), entry_tag=entry_tag, reason="below_minimum_stake", stake_amount=round(stake, 8))
            return 0.0
        self._send_audit_event("risk_approved", pair=pair, entry_rate=round(current_rate, 8), stake_amount=round(stake, 8), exposure=round(exposure, 6), entry_tag=entry_tag)
        return stake

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, min_stake: float | None, max_stake: float, current_entry_rate: float, current_exit_rate: float, current_entry_profit: float, current_exit_profit: float, **kwargs) -> tuple[float | None, str | None]:
        """Rebalance once per new daily candle using the research dead-band rule."""
        if getattr(trade, "has_open_orders", False):
            # Freqtrade calls this hook while an order is still pending. Sizing from a partly filled
            # position would double the order, so wait until the position is settled.
            return (None, None)
        row = self._latest_row(trade.pair)
        if row is None:
            return (None, None)
        candle_at = str(row.get("date", "unknown"))
        if trade.get_custom_data("last_rebalance_candle", default=None) == candle_at:
            return (None, None)
        trade.set_custom_data("last_rebalance_candle", candle_at)
        target = self._number(row, "exposure")
        budget = self._pair_budget()
        if target is None or target <= 0 or budget <= 0:
            return (None, None)  # a zero target is handled by the exit signal, not by resizing
        held_value = trade.amount * current_rate
        new_exposure = rebalanced_exposure(held_value / budget, target, self.trend.rebalance_band)
        delta = budget * new_exposure - held_value
        floor = min_stake or 0.0
        if delta > 0:
            stake = min(delta, max_stake)
            if stake >= floor and stake > 0:
                self._send_audit_event("trend_rebalance_requested", pair=trade.pair, trade_id=trade.id, direction="up", stake_amount=round(stake, 8), target_exposure=round(target, 6))
                return (stake, "trend_rebalance_up")
        elif delta < 0:
            reduce = -delta
            if reduce >= floor and held_value - reduce >= floor:
                # Freqtrade reads a negative stake as a share of the trade's cost basis, not of its
                # market value, so convert; otherwise requests on a profitable position are ignored.
                cost_basis_stake = reduce * trade.stake_amount / held_value
                self._send_audit_event("trend_rebalance_requested", pair=trade.pair, trade_id=trade.id, direction="down", stake_amount=round(reduce, 8), target_exposure=round(target, 6))
                return (-cost_basis_stake, "trend_rebalance_down")
        return (None, None)
