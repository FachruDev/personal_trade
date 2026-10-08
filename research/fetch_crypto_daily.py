import json, time, urllib.request, pandas as pd
from pathlib import Path
out = Path("data/daily"); out.mkdir(parents=True, exist_ok=True)
syms = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","LTCUSDT","TRXUSDT","LINKUSDT","DOGEUSDT","SOLUSDT","EOSUSDT","XLMUSDT","ETCUSDT","DASHUSDT","ZECUSDT","NEOUSDT","IOTAUSDT","VETUSDT","ATOMUSDT","AVAXUSDT"]
for s in syms:
    rows=[]; start=int(pd.Timestamp("2017-08-01").timestamp()*1000)
    while True:
        url=f"https://api.binance.com/api/v3/klines?symbol={s}&interval=1d&startTime={start}&limit=1000"
        try:
            d=json.load(urllib.request.urlopen(url,timeout=30))
        except Exception as e:
            print(s,"ERR",e); break
        if not d: break
        rows+=d; start=d[-1][0]+86400000
        if len(d)<1000: break
        time.sleep(0.2)
    if rows:
        df=pd.DataFrame(rows).iloc[:,:6]; df.columns=["t","o","h","l","c","v"]
        df["t"]=pd.to_datetime(df["t"],unit="ms"); df=df.set_index("t").astype(float)
        df.to_parquet(out/f"{s}.parquet"); print(s,len(df),df.index[0].date(),df.index[-1].date())
