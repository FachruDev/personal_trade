import pandas as pd, numpy as np
for sym in ["BTC","ETH"]:
    df=pd.read_feather(f"../freqtrade/data/binance/{sym}_USDT-1h.feather")
    df=df.set_index("date"); c=df["close"]; v=df["volume"]
    e=lambda n:c.ewm(span=n,adjust=False).mean()
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    rsi=100-100/(1+up/dn)
    macd=e(12)-e(26); hist=macd-macd.ewm(span=9,adjust=False).mean()
    cond=(c>e(800))&(e(20)>e(50))&(rsi.between(45,65))&(hist>0)&(hist>=hist.shift())&(v>v.rolling(20).mean())
    print(sym,"bars",len(c),"signal bars",int(cond.sum()),f"({cond.mean():.1%})")
    for h in [6,24,72]:
        f=c.shift(-h)/c-1
        print(f"  fwd {h:>2}h  signal mean {f[cond].mean()*100:+.3f}%  all-bars mean {f.mean()*100:+.3f}%  |  round-trip cost 0.20%+slip   hit-rate {(f[cond]>0).mean():.2f}")
