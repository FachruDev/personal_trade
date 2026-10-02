from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MarketRegime(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"


class Signal(StrEnum):
    BUY = "buy"
    HOLD = "hold"


@dataclass(frozen=True)
class EntrySnapshot:
    ema20: float
    ema50: float
    rsi: float
    macd_histogram: float
    previous_macd_histogram: float
    volume: float
    volume_sma: float


def classify_regime(close: float, ema50: float, ema200: float, adx: float, atr_percent: float, high_volatility_threshold: float = 0.06, trend_adx_threshold: float = 20) -> MarketRegime:
    if atr_percent >= high_volatility_threshold:
        return MarketRegime.HIGH_VOLATILITY
    if close > ema200 and ema50 > ema200 and adx > trend_adx_threshold:
        return MarketRegime.BULL
    if close < ema200 and ema50 < ema200:
        return MarketRegime.BEAR
    return MarketRegime.SIDEWAYS


def evaluate_entry(regime: MarketRegime, snapshot: EntrySnapshot) -> Signal:
    conditions = (regime is MarketRegime.BULL, snapshot.ema20 > snapshot.ema50, 45 <= snapshot.rsi <= 65, snapshot.macd_histogram > 0, snapshot.macd_histogram >= snapshot.previous_macd_histogram, snapshot.volume > snapshot.volume_sma)
    return Signal.BUY if all(conditions) else Signal.HOLD
