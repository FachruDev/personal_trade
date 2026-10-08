"""Rebuild daily mark-to-market equity from a Freqtrade backtest result zip.

Freqtrade's headline drawdown figures use closed trades; this uses every order plus daily closes so it
is comparable with the research model. Usage: python 11_engine_mark_to_market.py result.zip [...]
"""
import json, sys, zipfile
import numpy as np, pandas as pd

DATA = "../freqtrade/data/binance"
FEE = 0.001

def equity_from_result(path: str) -> pd.Series:
    z = zipfile.ZipFile(path)
    name = [n for n in z.namelist() if n.endswith(".json") and "config" not in n and "meta" not in n][0]
    strat = next(iter(json.load(z.open(name))["strategy"].values()))
    start_cash = float(strat["starting_balance"])
    orders = sorted(
        (o["order_filled_timestamp"], t["pair"], o["ft_order_side"], o["amount"], o["cost"])
        for t in strat["trades"] for o in t["orders"] if o.get("order_filled_timestamp")
    )
    closes = {}
    for pair in {o[1] for o in orders}:
        df = pd.read_feather(f"{DATA}/{pair.replace('/', '_')}-1d.feather").set_index("date")["close"]
        df.index = df.index.tz_convert("UTC")
        closes[pair] = df
    first = pd.Timestamp(orders[0][0], unit="ms", tz="UTC").normalize()
    last = pd.Timestamp(strat.get("backtest_end") or closes[next(iter(closes))].index[-1])
    last = last.tz_localize("UTC") if last.tzinfo is None else last.tz_convert("UTC")
    days = pd.date_range(first, last.normalize(), freq="D", tz="UTC")
    cash, held, i, out = start_cash, {p: 0.0 for p in closes}, 0, []
    for day in days:
        while i < len(orders) and pd.Timestamp(orders[i][0], unit="ms", tz="UTC") <= day:
            _, pair, side, amount, cost = orders[i]
            if side == "buy":
                cash -= cost * (1 + FEE); held[pair] += amount
            else:
                cash += cost * (1 - FEE); held[pair] -= amount
            i += 1
        value = cash + sum(held[p] * float(closes[p].get(day, np.nan)) for p in held if held[p] > 1e-12 and day in closes[p].index)
        out.append(value)
    return pd.Series(out, index=days)

def summarize(path: str) -> str:
    eq = equity_from_result(path)
    r = eq.pct_change().dropna()
    yrs = len(eq) / 365
    dd = (eq / eq.cummax() - 1).min()
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    return f"{path:46s} CAGR {cagr:6.1%}  MTM maxDD {dd:6.1%}  Sharpe {r.mean()/r.std()*365**.5:4.2f}  final {eq.iloc[-1]:8.1f}"

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(summarize(p))
