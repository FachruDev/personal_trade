from trading_core.strategy import EntrySnapshot, MarketRegime, Signal, classify_regime, evaluate_entry


def test_bull_regime_requires_trend_and_adx() -> None:
    assert classify_regime(110, 105, 100, 25, 0.02) is MarketRegime.BULL
    assert classify_regime(110, 105, 100, 25, 0.07) is MarketRegime.HIGH_VOLATILITY
    assert classify_regime(90, 95, 100, 25, 0.02) is MarketRegime.BEAR


def test_entry_needs_all_quant_conditions() -> None:
    snapshot = EntrySnapshot(110, 100, 55, 2, 1, 150, 100)
    assert evaluate_entry(MarketRegime.BULL, snapshot) is Signal.BUY
    assert evaluate_entry(MarketRegime.BULL, EntrySnapshot(110, 100, 71, 2, 1, 150, 100)) is Signal.HOLD
    assert evaluate_entry(MarketRegime.SIDEWAYS, snapshot) is Signal.HOLD
