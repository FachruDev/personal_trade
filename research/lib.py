import numpy as np, pandas as pd
from pathlib import Path

D = Path(__file__).parent / "data" / "daily"
COST = 0.0015  # 0.10% fee + 0.05% slippage per side, charged on traded notional
ANN = 365


def load():
    o, c = {}, {}
    for p in sorted(D.glob("*.parquet")):
        df = pd.read_parquet(p).iloc[:-1]  # drop today's incomplete candle
        o[p.stem], c[p.stem] = df["o"], df["c"]
    return pd.DataFrame(o), pd.DataFrame(c)


OPEN, CLOSE = load()
RET_OO = OPEN.shift(-1) / OPEN - 1  # return from open t to open t+1


def run(w: pd.DataFrame, cost=COST):
    """w[t] = target weights decided at close t, traded at open t+1, earning open t+1 -> open t+2.
    Pay day: pnl[t+1] = w[t] . RET_OO[t+1]."""
    w = w.reindex(CLOSE.index).fillna(0.0)
    held = w.shift(1)
    gross = (held * RET_OO).sum(axis=1, min_count=1).fillna(0.0)
    turn = (held - held.shift(1)).abs().sum(axis=1).fillna(0.0)
    return gross - turn * cost, turn


def stats(r: pd.Series, turn=None):
    r = r.dropna()
    if len(r) < 30 or r.std() == 0:
        return dict(CAGR=np.nan, Vol=np.nan, Sharpe=np.nan, MaxDD=np.nan, Calmar=np.nan, Turn_yr=np.nan)
    eq = (1 + r).cumprod()
    yrs = len(r) / ANN
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(ANN)
    return dict(CAGR=cagr, Vol=r.std() * np.sqrt(ANN), Sharpe=sh, MaxDD=dd,
                Calmar=cagr / abs(dd) if dd < 0 else np.nan,
                Turn_yr=(turn.loc[r.index].sum() / yrs) if turn is not None else np.nan)


def sma(x, n): return x.rolling(n).mean()
def rvol(n=20): return CLOSE.pct_change().rolling(n).std() * np.sqrt(ANN)


def block_boot_sharpe(r, n=2000, block=20, seed=0):
    r = r.dropna().values
    rng = np.random.default_rng(seed)
    T = len(r); k = int(np.ceil(T / block)); out = np.empty(n)
    for i in range(n):
        st = rng.integers(0, T - block, k)
        s = np.concatenate([r[a:a + block] for a in st])[:T]
        out[i] = s.mean() / s.std() * np.sqrt(ANN)
    return np.percentile(out, [5, 50, 95])
