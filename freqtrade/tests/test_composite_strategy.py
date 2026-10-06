from __future__ import annotations

import unittest
from unittest.mock import patch

from pandas import DataFrame, isna
import requests

from CompositeTrendPullbackStrategy import CompositeTrendPullbackStrategy


def valid_rows() -> DataFrame:
    return DataFrame(
        [
            {
                "close": 100.0,
                "low": 99.9,
                "ema20": 100.0,
                "ema50": 95.0,
                "rsi": 45.0,
                "macdhist": 1.0,
                "volume": 120.0,
                "volume_sma": 100.0,
                "atr": 1.0,
                "close_4h": 120.0,
                "ema50_4h": 110.0,
                "ema200_4h": 100.0,
                "adx_4h": 25.0,
                "atr_pct_4h": 0.02,
                "atr_pct_normal_low_4h": 0.01,
                "atr_pct_normal_high_4h": 0.03,
            },
            {
                "close": 100.5,
                "low": 100.1,
                "ema20": 100.0,
                "ema50": 95.0,
                "rsi": 48.0,
                "macdhist": 1.2,
                "volume": 120.0,
                "volume_sma": 100.0,
                "atr": 1.0,
                "close_4h": 120.0,
                "ema50_4h": 110.0,
                "ema200_4h": 100.0,
                "adx_4h": 25.0,
                "atr_pct_4h": 0.02,
                "atr_pct_normal_low_4h": 0.01,
                "atr_pct_normal_high_4h": 0.03,
            },
        ]
    )


class CompositeTrendPullbackTests(unittest.TestCase):
    @staticmethod
    def evaluate(dataframe: DataFrame) -> DataFrame:
        # The rule itself is deterministic and does not need Freqtrade's full
        # runtime configuration to be unit-tested.
        return CompositeTrendPullbackStrategy.populate_entry_trend(CompositeTrendPullbackStrategy, dataframe, {})

    def test_complete_composite_rule_enters(self) -> None:
        dataframe = self.evaluate(valid_rows())
        self.assertEqual(dataframe.iloc[-1]["enter_long"], 1)
        self.assertEqual(dataframe.iloc[-1]["enter_tag"], "composite_trend_pullback")

    def test_each_required_condition_blocks_entry(self) -> None:
        mutations = {
            "close_4h": 90.0,
            "adx_4h": 20.0,
            "atr_pct_4h": 0.04,
            "ema20": 94.0,
            "low": 102.0,
            "rsi": 56.0,
            "macdhist": 0.9,
            "volume": 109.0,
            "close": 102.0,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                dataframe = valid_rows()
                dataframe.loc[dataframe.index[-1], field] = value
                evaluated = self.evaluate(dataframe)
                self.assertTrue(isna(evaluated.iloc[-1]["enter_long"]))

    def test_active_paper_strategy_is_not_the_research_strategy(self) -> None:
        self.assertNotEqual(CompositeTrendPullbackStrategy.__name__, "LimitedRiskRegimeRiskStrategy")

    def test_startup_window_covers_90_day_informative_percentile(self) -> None:
        self.assertGreaterEqual(CompositeTrendPullbackStrategy.startup_candle_count, 2_160)

    @patch("CompositeTrendPullbackStrategy.requests.get", side_effect=requests.RequestException())
    def test_context_snapshot_failure_is_advisory_only(self, _get) -> None:
        self.assertEqual(CompositeTrendPullbackStrategy._context_shadow(), {"available": False, "mode": "shadow"})


if __name__ == "__main__":
    unittest.main()
