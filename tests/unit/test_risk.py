from datetime import datetime, timedelta, timezone

from trading_core.risk import RiskSettings, calculate_position_size, cooldown_active, daily_loss_locked


def test_position_size_limits_loss_to_half_percent() -> None:
    stake = calculate_position_size(1000, 100, 98, RiskSettings())
    assert stake == 250
    assert stake * ((100 - 98) / 100) == 5


def test_position_size_rejects_invalid_stop() -> None:
    assert calculate_position_size(1000, 100, 101) == 0


def test_daily_loss_gate_uses_configured_limit() -> None:
    assert daily_loss_locked(-0.03)
    assert not daily_loss_locked(-0.029)


def test_cooldown_last_six_hours_after_third_loss() -> None:
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    assert cooldown_active(3, now - timedelta(hours=5), now)
    assert not cooldown_active(3, now - timedelta(hours=6), now)
