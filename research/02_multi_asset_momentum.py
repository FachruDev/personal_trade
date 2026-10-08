from lib import *
pd.set_option("display.width",220)
elig=(CLOSE.notna().cumsum()>=200)&CLOSE.notna()
N=elig.sum(axis=1).clip(lower=1)
def weekly(w):
    mon=pd.Series(w.index.dayofweek==0,index=w.index)
    return w[mon].reindex(w.index).ffill().fillna(0.0)
def ew_trend(L):
    sig=((CLOSE>sma(CLOSE,L))&elig).astype(float)
    return sig.div(N,axis=0)
def ew_bh():
    return elig.astype(float).div(N,axis=0)
def xs_mom(R,k,L=100):
    ret=CLOSE.pct_change(R).where(elig)
    ok=(CLOSE>sma(CLOSE,L))&elig
    rk=ret.where(ok).rank(axis=1,ascending=False)
    return weekly(((rk<=k)).astype(float)/k)
periods={"2019-21":("2019-01-01","2021-12-31"),"2022-23":("2022-01-01","2023-12-31"),"2024-26":("2024-01-01","2026-12-31"),"ALL":("2019-01-01","2026-12-31")}
cands={"EW buy&hold (biased)":ew_bh()}
for L in [50,100,150,200]: cands[f"EW trend SMA{L}"]=ew_trend(L)
for R in [30,60,90]:
    for k in [3,5]: cands[f"XSmom R{R} top{k} +SMA100"]=xs_mom(R,k)
rows=[]
for name,w in cands.items():
    r,t=run(w)
    row={"strat":name}
    for p,(a,b) in periods.items():
        s=stats(r[a:b],t)
        row[f"{p} Sh"]=s["Sharpe"]; row[f"{p} CAGR"]=s["CAGR"]; row[f"{p} DD"]=s["MaxDD"]
    row["Turn/yr"]=stats(r["2019":],t)["Turn_yr"]
    rows.append(row)
df=pd.DataFrame(rows).set_index("strat")
print(df.round(2).to_string())
