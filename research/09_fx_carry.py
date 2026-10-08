import numpy as np, pandas as pd
cc={"USD":"US","EUR":"EZ","GBP":"GB","JPY":"JP","CHF":"CH","AUD":"AU","CAD":"CA"}
r={}
for k,v in cc.items():
    d=pd.read_csv(f"data/rates/IR3TIB01{v}M156N.csv",index_col=0,parse_dates=True).iloc[:,0].astype(float)
    r[k]=d
R=pd.DataFrame(r)["1999":].ffill()/100.0           # annual decimal, monthly
R=R.shift(1)                                       # 1-month publication lag
fx=pd.read_parquet("data/fx/usd_base.parquet").dropna(); fx=fx[~fx.index.duplicated()]
px=(1.0/fx)[["EUR","GBP","JPY","CHF","AUD","CAD"]]
ret=px.pct_change()
rd=R.reindex(ret.index,method="ffill")
carry_d=(rd[ret.columns].sub(rd["USD"],axis=0))/365.0   # daily carry vs USD for long position
def run(k=2,markup=0.0,cost=0.0003,lev_target=0.10,start="2002-06-01"):
    idx=ret.index
    mend=pd.Series(idx,index=idx).groupby([idx.year,idx.month]).max().values   # last trading day of each month
    w=pd.DataFrame(np.nan,index=idx,columns=ret.columns)
    for dt in mend:
        if dt<pd.Timestamp(start): continue
        rt=rd.loc[dt,ret.columns].dropna()
        row=pd.Series(0.0,index=ret.columns)
        if len(rt)>=2*k:
            o=rt.sort_values(); row[o.index[-k:]]=1.0/k; row[o.index[:k]]=-1.0/k
        w.loc[dt]=row
    w=w.ffill().fillna(0.0)
    held=w.shift(2)                                     # signal at month end, trade 1 day later, earn after
    pnl=(held*(ret+carry_d)).sum(axis=1) - held.abs().sum(axis=1)*markup/365.0
    turn=(w.shift(2)-w.shift(3)).abs().sum(axis=1)
    pnl=(pnl-turn*cost)[start:]
    sc=lev_target/(pnl.std()*np.sqrt(252)); return pnl*sc, sc
def st(x):
    eq=(1+x).cumprod(); yrs=len(x)/252
    return f"CAGR {eq.iloc[-1]**(1/yrs)-1:6.1%}  Sharpe {x.mean()/x.std()*np.sqrt(252):5.2f}  MaxDD {(eq/eq.cummax()-1).min():6.1%}"
for mk in [0.0,0.015]:
    x,sc=run(markup=mk); print(f"carry top2/bottom2, markup {mk:.1%}/yr, scaled x{sc:.1f} to 10% vol:\n  ALL   ",st(x))
    for a,b in [("2002-06","2008-12"),("2009","2015"),("2016","2026")]:
        print(f"  {a}-{b}",st(x[a:b]))
x,_=run(markup=0.0)
# decomposition: unscaled spot-only vs carry-only contribution
