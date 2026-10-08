import math

from trading_core.trend import TrendSettings, rebalanced_exposure, target_exposure, trend_score, volatility_scale


def rising(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + step * i for i in range(n)]


def test_trend_score_is_zero_without_full_history() -> None:
    assert trend_score(rising(149), (50, 100, 150)) == 0.0


def test_trend_score_counts_averages_below_the_last_close() -> None:
    assert trend_score(rising(200), (50, 100, 150)) == 1.0
    assert trend_score(list(reversed(rising(200))), (50, 100, 150)) == 0.0
    # Uptrend ending near 299, then a pullback to 270: below the 50-day average (~274)
    # but still above the 100-day (~249) and 150-day (~225) averages.
    assert trend_score(rising(200) + [270.0], (50, 100, 150)) == 2 / 3
    # A deeper drop to 150 falls below all three averages.
    assert trend_score(rising(200) + [150.0], (50, 100, 150)) == 0.0


def test_volatility_scale_is_capped_at_one_and_never_levers() -> None:
    flat = [100.0] * 30
    assert volatility_scale(flat, 0.40, 20) == 1.0
    calm = [100.0 * (1 + 0.001 * ((-1) ** i)) for i in range(30)]
    assert volatility_scale(calm, 0.40, 20) == 1.0


def test_volatility_scale_shrinks_when_realised_volatility_exceeds_target() -> None:
    wild = [100.0 * (1.08 if i % 2 else 0.93) ** 1 for i in range(1, 31)]
    scale = volatility_scale(wild, 0.40, 20)
    assert 0 < scale < 0.2
    assert math.isclose(scale, 0.40 / (_annualised(wild, 20)), rel_tol=1e-9)


def test_volatility_scale_is_zero_while_history_is_short() -> None:
    assert volatility_scale([100.0] * 10, 0.40, 20) == 0.0


def test_target_exposure_combines_trend_and_volatility() -> None:
    settings = TrendSettings()
    assert target_exposure(list(reversed(rising(200))), settings) == 0.0
    steady = [100 * 1.003**i for i in range(220)]
    assert math.isclose(target_exposure(steady, settings), 1.0)


def test_dead_band_ignores_small_changes_but_always_exits_and_enters() -> None:
    assert rebalanced_exposure(0.50, 0.55, 0.10) == 0.50
    assert rebalanced_exposure(0.50, 0.70, 0.10) == 0.70
    assert rebalanced_exposure(0.50, 0.0, 0.10) == 0.0
    assert rebalanced_exposure(0.0, 0.04, 0.10) == 0.0
    assert rebalanced_exposure(0.0, 0.06, 0.10) == 0.06


def _annualised(closes: list[float], window: int) -> float:
    from statistics import stdev

    tail = closes[-(window + 1):]
    returns = [tail[i] / tail[i - 1] - 1 for i in range(1, len(tail))]
    return stdev(returns) * math.sqrt(365)
