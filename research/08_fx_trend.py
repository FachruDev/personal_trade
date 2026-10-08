import numpy as np, pandas as pd
fx=pd.read_parquet("data/fx/usd_base.parquet").dropna(); fx=fx[~fx.index.duplicated()]
px=1.0/fx           # value of 1 unit of foreign currency in USD
R=px.pct_change()   # daily return of long-foreign / short-USD
COST=0.0003
def run(w):
    held=w.shift(2)             # signal at t, trade next fix, earn following day  (conservative 1-day lag)
    pnl=(held*R).sum(axis=1)
    turn=(w.shift(2)-w.shift(3)).abs().sum(axis=1)
    return pnl-turn*COST, turn
def st(r,t):
    r=r.dropna(); yrs=len(r)/252; eq=(1+r).cumprod()
    return dict(CAGR=eq.iloc[-1]**(1/yrs)-1,Vol=r.std()*np.sqrt(252),Sharpe=r.mean()/r.std()*np.sqrt(252),MaxDD=(eq/eq.cummax()-1).min(),Turn=t.loc[r.index].sum()/yrs)
vol=R.rolling(60).std()*np.sqrt(252)
per={"2000-09":("2000-01-01","2009-12-31"),"2010-19":("2010-01-01","2019-12-31"),"2020-26":("2020-01-01","2026-12-31"),"ALL":("2000-01-01","2026-12-31")}
rows=[]
for L in [60,120,250]:
    sgn=np.sign(px/px.shift(L)-1)
    w=(sgn*(0.10/vol)).div(px.shape[1],axis=1) if False else (sgn*(0.10/vol))/px.shape[1]
    r,t=run(w)
    row={"strat":f"TSMOM L{L}"}
    for p,(a,b) in per.items():
        s=st(r[a:b],t); row[f"{p} Sh"]=s["Sharpe"]; row[f"{p} CAGR"]=s["CAGR"]; row[f"{p} DD"]=s["MaxDD"]
    row["Vol"]=st(r,t)["Vol"]; row["Turn/yr"]=st(r,t)["Turn"]; rows.append(row)
# naive: long-only SMA100 on EURUSD-like majors is not meaningful; benchmark = equal-weight long all vs USD
w=pd.DataFrame(1.0/px.shape[1],index=px.index,columns=px.columns); r,t=run(w)
row={"strat":"EW long vs USD (benchmark)"}
for p,(a,b) in per.items():
    s=st(r[a:b],t); row[f"{p} Sh"]=s["Sharpe"]; row[f"{p} CAGR"]=s["CAGR"]; row[f"{p} DD"]=s["MaxDD"]
rows.append(row)
pd.set_option("display.width",220)
print(pd.DataFrame(rows).set_index("strat").round(2).to_string())
