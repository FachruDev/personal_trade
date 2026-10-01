from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RiskSettings:
    risk_per_trade: float = 0.005
    max_risk_per_trade: float = 0.01
    max_open_trades: int = 2
    max_portfolio_risk: float = 0.02
    daily_loss_limit: float = 0.03
    consecutive_loss_limit: int = 3
    cooldown_hours: int = 6
    atr_stop_multiple: float = 1.5
    take_profit_one_r: float = 1.5
    take_profit_two_r: float = 2.5


def calculate_position_size(wallet_balance: float, entry_price: float, stop_price: float, settings: RiskSettings = RiskSettings(), minimum_stake: float | None = None, maximum_stake: float | None = None) -> float:
    """Return quote-currency stake that limits a stopped trade to the risk budget."""
    if wallet_balance <= 0 or entry_price <= 0 or stop_price <= 0 or stop_price >= entry_price:
        return 0.0
    risk_budget = wallet_balance * min(settings.risk_per_trade, settings.max_risk_per_trade)
    price_risk_fraction = (entry_price - stop_price) / entry_price
    stake = risk_budget / price_risk_fraction
    if maximum_stake is not None:
        stake = min(stake, maximum_stake)
    return 0.0 if minimum_stake is not None and stake < minimum_stake else max(stake, 0.0)


def daily_loss_locked(realized_pnl_ratio: float, settings: RiskSettings = RiskSettings()) -> bool:
    return realized_pnl_ratio <= -settings.daily_loss_limit


def cooldown_active(consecutive_losses: int, last_loss_at: datetime | None, now: datetime, settings: RiskSettings = RiskSettings()) -> bool:
    return consecutive_losses >= settings.consecutive_loss_limit and last_loss_at is not None and now < last_loss_at + timedelta(hours=settings.cooldown_hours)
