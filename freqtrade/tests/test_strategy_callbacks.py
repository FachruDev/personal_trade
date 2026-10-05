from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from RegimeRiskStrategy import RegimeRiskStrategy


class FakeTrade:
    open_rate = 100.0
    id = 1

    def __init__(self) -> None:
        self.data = {"initial_risk_ratio": 0.02}

    def get_custom_data(self, key: str, default=None):
        return self.data.get(key, default)

    def set_custom_data(self, key: str, value) -> None:
        self.data[key] = value


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"recommendation": {"decision": "NEUTRAL", "risk_multiplier": 1.0}}


class TrailingStopCallbackTests(unittest.TestCase):
    def test_startup_window_covers_the_informative_ema_200(self) -> None:
        self.assertGreaterEqual(RegimeRiskStrategy.startup_candle_count, 1_000)

    def test_trailing_stop_starts_after_first_reward_target(self) -> None:
        strategy = RegimeRiskStrategy.__new__(RegimeRiskStrategy)
        strategy._send_audit_event = lambda *args, **kwargs: None
        trade = FakeTrade()

        result = strategy.custom_stoploss(
            "BTC/USDT", trade, None, current_rate=105.0, current_profit=0.05, after_fill=False
        )

        self.assertTrue(trade.data["trailing_stop_logged"])
        self.assertGreater(result, -0.05)


class ContextShadowTests(unittest.TestCase):
    @patch("RegimeRiskStrategy.requests.get", return_value=FakeResponse())
    def test_nested_context_fusion_response_is_recorded(self, _get) -> None:
        self.assertEqual(
            RegimeRiskStrategy._context_shadow(),
            {"available": True, "recommendation": "NEUTRAL", "risk_multiplier": 1.0},
        )

    @patch("RegimeRiskStrategy.requests.get", side_effect=requests.RequestException())
    def test_context_failure_is_advisory_only(self, _get) -> None:
        self.assertEqual(RegimeRiskStrategy._context_shadow(), {"available": False})


if __name__ == "__main__":
    unittest.main()
