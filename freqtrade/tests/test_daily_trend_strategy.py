from __future__ import annotations

import math
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests
from pandas import DataFrame, Series

from DailyTrendVolStrategy import DailyTrendVolStrategy
from trading_core.trend import target_exposure


def synthetic_prices(days: int = 400, seed: int = 7) -> list[float]:
    rng = random.Random(seed)
    price, series = 100.0, []
    for _ in range(days):
        price *= 1 + rng.gauss(0.0008, 0.025)
        series.append(price)
    return series


class FakeTrade:
    id = 1
    pair = "BTC/USDT"

    def __init__(self, amount: float) -> None:
        self.amount = amount
        self.data: dict = {}

    def get_custom_data(self, key: str, default=None):
        return self.data.get(key, default)

    def set_custom_data(self, key: str, value) -> None:
        self.data[key] = value


class FakeWallets:
    def __init__(self, total: float) -> None:
        self.total = total

    def get_total_stake_amount(self) -> float:
        return self.total


def make_strategy(exposure: float, candle: str = "2026-01-01", wallet: float = 1000.0) -> DailyTrendVolStrategy:
    strategy = DailyTrendVolStrategy.__new__(DailyTrendVolStrategy)
    strategy._send_audit_event = lambda *args, **kwargs: None
    strategy.wallets = FakeWallets(wallet)
    strategy._latest_row = lambda pair: Series({"date": candle, "exposure": exposure})
    return strategy


def adjust(strategy: DailyTrendVolStrategy, trade: FakeTrade, rate: float = 100.0):
    return strategy.adjust_trade_position(
        trade, None, rate, 0.0, 10.0, 10_000.0, rate, rate, 0.0, 0.0
    )


class IndicatorTests(unittest.TestCase):
    def test_vectorised_exposure_matches_the_pure_core_rule(self) -> None:
        prices = synthetic_prices()
        strategy = DailyTrendVolStrategy.__new__(DailyTrendVolStrategy)
        frame = strategy.populate_indicators(DataFrame({"close": prices}), {})
        mismatches = [
            i
            for i in range(len(prices))
            if not math.isclose(frame["exposure"].iloc[i], target_exposure(prices[: i + 1], strategy.trend), abs_tol=1e-9)
        ]
        self.assertEqual(mismatches, [])

    def test_exit_signal_fires_only_when_every_average_is_broken(self) -> None:
        prices = [100 + i for i in range(200)] + [50.0]
        strategy = DailyTrendVolStrategy.__new__(DailyTrendVolStrategy)
        frame = strategy.populate_indicators(DataFrame({"close": prices, "volume": [1.0] * len(prices)}), {})
        frame = strategy.populate_exit_trend(frame, {})
        self.assertEqual(frame["exit_long"].iloc[-1], 1)
        # Once 150 candles of history exist, a rising series never triggers an exit.
        self.assertTrue(frame["exit_long"].iloc[149:-1].isna().all())

    def test_entry_requires_trend_exposure_and_volume(self) -> None:
        prices = [100 + i for i in range(220)]
        strategy = DailyTrendVolStrategy.__new__(DailyTrendVolStrategy)
        frame = strategy.populate_indicators(DataFrame({"close": prices, "volume": [1.0] * 219 + [0.0]}), {})
        frame = strategy.populate_entry_trend(frame, {})
        self.assertEqual(frame["enter_long"].iloc[-2], 1)
        self.assertTrue(frame["enter_long"].iloc[:149].isna().all())  # no entry before 150 candles
        self.assertTrue(isinstance(frame["enter_long"].iloc[-1], float) and math.isnan(frame["enter_long"].iloc[-1]))


class RebalanceTests(unittest.TestCase):
    def test_rebalances_up_when_target_exceeds_held_by_more_than_the_band(self) -> None:
        strategy = make_strategy(exposure=0.90)  # budget per pair = 500; target 450
        trade = FakeTrade(amount=2.0)  # held 200 -> 0.40 of budget
        stake, tag = adjust(strategy, trade)
        self.assertEqual(tag, "trend_rebalance_up")
        self.assertAlmostEqual(stake, 250.0)

    def test_rebalances_down_with_a_negative_stake(self) -> None:
        strategy = make_strategy(exposure=0.30)  # target 150
        trade = FakeTrade(amount=4.0)  # held 400 -> 0.80
        stake, tag = adjust(strategy, trade)
        self.assertEqual(tag, "trend_rebalance_down")
        self.assertAlmostEqual(stake, -250.0)

    def test_small_drift_inside_the_band_does_nothing(self) -> None:
        strategy = make_strategy(exposure=0.55)
        trade = FakeTrade(amount=2.7)  # held 270 of a 500 budget -> 0.54, within 0.10 of 0.55
        self.assertEqual(adjust(strategy, trade), (None, None))

    def test_acts_at_most_once_per_daily_candle(self) -> None:
        strategy = make_strategy(exposure=0.90)
        trade = FakeTrade(amount=2.0)
        self.assertIsNotNone(adjust(strategy, trade)[0])
        self.assertEqual(adjust(strategy, trade), (None, None))

    def test_zero_target_is_left_to_the_exit_signal(self) -> None:
        strategy = make_strategy(exposure=0.0)
        self.assertEqual(adjust(strategy, FakeTrade(amount=4.0)), (None, None))


class FakeResponse:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"enabled": self.enabled}


def strategy_in_mode(mode: str) -> DailyTrendVolStrategy:
    strategy = DailyTrendVolStrategy.__new__(DailyTrendVolStrategy)
    strategy._send_audit_event = lambda *args, **kwargs: None
    strategy.dp = SimpleNamespace(runmode=SimpleNamespace(value=mode))
    return strategy


def confirm(strategy: DailyTrendVolStrategy) -> bool:
    return strategy.confirm_trade_entry("BTC/USDT", "limit", 1.0, 100.0, "GTC", None, "daily_trend", "long")


class KillSwitchTests(unittest.TestCase):
    @patch("DailyTrendVolStrategy.requests.get", side_effect=AssertionError("must not be called"))
    def test_backtest_never_calls_the_api(self, _get) -> None:
        self.assertTrue(confirm(strategy_in_mode("backtest")))

    @patch("DailyTrendVolStrategy.requests.get", return_value=FakeResponse(enabled=False))
    def test_dry_run_allows_entry_when_switch_is_clear(self, _get) -> None:
        self.assertTrue(confirm(strategy_in_mode("dry_run")))

    @patch("DailyTrendVolStrategy.requests.get", return_value=FakeResponse(enabled=True))
    def test_dry_run_blocks_entry_when_switch_is_enabled(self, _get) -> None:
        self.assertFalse(confirm(strategy_in_mode("dry_run")))

    @patch("DailyTrendVolStrategy.requests.get", side_effect=requests.RequestException())
    def test_live_fails_closed_when_api_is_unreachable(self, _get) -> None:
        self.assertFalse(confirm(strategy_in_mode("live")))


if __name__ == "__main__":
    unittest.main()
