import pandas as pd, numpy as np
for sym in ["BTC","ETH"]:
    df=pd.read_feather(f"../freqtrade/data/binance/{sym}_USDT-1h.feather").set_index("date")
    r=df["close"].pct_change().dropna(); rng=(df["high"]-df["low"])/df["close"]
    print(sym,f"annual vol {r.std()*np.sqrt(24*365):.0%} | median 1H range {rng.median()*100:.2f}% | mean |1H return| {r.abs().mean()*100:.3f}% | std 1H {r.std()*100:.3f}%")
    for h,lab in [(1,"1H"),(4,"4H"),(24,"1D")]:
        rh=df["close"].pct_change(h).dropna()
        print(f"   {lab}: typical move (mean abs) {rh.abs().mean()*100:.2f}%  -> cost 0.20%+slip is {0.25/ (rh.abs().mean()*100):.0%} of a typical move")
