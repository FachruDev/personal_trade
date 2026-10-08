import json, urllib.request, pandas as pd, io
UA={'User-Agent':'personal-research-script/1.0 (daily fx backtest)'}
def get(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60)
from pathlib import Path
Path("data/fx").mkdir(parents=True, exist_ok=True)
cur=["EUR","GBP","JPY","CHF","AUD","NZD","CAD","SEK","NOK"]
frames=[]
for a,b in [("1999-01-04","2007-12-31"),("2008-01-01","2016-12-31"),("2017-01-01","2026-10-08")]:
    u=f"https://api.frankfurter.dev/v1/{a}..{b}?base=USD&symbols={','.join(cur)}"
    d=json.load(get(u))["rates"]
    frames.append(pd.DataFrame(d).T)
fx=pd.concat(frames); fx.index=pd.to_datetime(fx.index); fx=fx.sort_index().astype(float); fx=fx[~fx.index.duplicated()]  # range edges repeat a date
fx.to_parquet("data/fx/usd_base.parquet"); print(fx.shape, fx.index[0].date(), fx.index[-1].date())
# Interest rates are NOT fetched here: download each IR3TIB01xxM156N series as CSV from FRED
# (https://fred.stlouisfed.org/series/IR3TIB01USM156N etc.) into data/rates/. See README.md.
