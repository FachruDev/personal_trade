from trading_core.composite import CompositeDecision, CompositeScoreInput, score_composite_pullback


def full_snapshot(**changes):
    defaults = dict(
        bullish_regime=True,
        rsi_recovering=True,
        macd_improving=True,
        volume_confirmed=True,
        volatility_normal=True,
        pullback_structure=True,
    )
    defaults.update(changes)
    return CompositeScoreInput(**defaults)


def test_full_composite_score_is_auditable_but_needs_entry_gate() -> None:
    score = score_composite_pullback(full_snapshot(), entry_allowed=True)
    assert score.total == 100
    assert score.decision is CompositeDecision.ENTRY_CANDIDATE


def test_score_can_watch_without_permitting_an_order() -> None:
    score = score_composite_pullback(full_snapshot(volume_confirmed=False), entry_allowed=False)
    assert score.total == 80
    assert score.decision is CompositeDecision.WATCH


def test_non_bullish_context_is_held() -> None:
    score = score_composite_pullback(full_snapshot(bullish_regime=False), entry_allowed=False)
    assert score.decision is CompositeDecision.HOLD
