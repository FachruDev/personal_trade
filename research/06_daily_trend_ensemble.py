from lib import *
pd.set_option("display.width",200)
START="2018-03-01"
SYMS=["BTCUSDT","ETHUSDT"]
def target_weights(sym, lookbacks=(50,100,150), tvol=0.40, vol_n=20, band=0.10):
    c=CLOSE[sym]
    sig=sum((c>sma(c,L)).astype(float) for L in lookbacks)/len(lookbacks)
    sig=sig.where(sma(c,max(lookbacks)).notna(),0.0)
    scale=(tvol/(c.pct_change().rolling(vol_n).std()*np.sqrt(ANN))).clip(upper=1.0)
    raw=(sig*scale).fillna(0.0)
    out=raw.copy(); cur=0.0
    for i,(d,v) in enumerate(raw.items()):          # dead-band: trade only if change > band, or exit to/from zero
        if (abs(v-cur)>band) or (v==0 and cur!=0) or (cur==0 and v>0.0 and v>band/2):
            cur=v
        out.iloc[i]=cur
    return out
def build(lookbacks=(50,100,150),tvol=0.40,band=0.10,split=0.5):
    w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns)
    for s in SYMS: w[s]=target_weights(s,lookbacks,tvol,band=band)*split
    return w
def bh(split=0.5):
    w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns)
    for s in SYMS: w[s]=split
    return w
periods={"2018":("2018-03-01","2018-12-31"),"2019-21":("2019-01-01","2021-12-31"),"2022-23":("2022-01-01","2023-12-31"),"2024-26":("2024-01-01","2026-12-31"),"ALL":(START,"2026-12-31")}
def report(name,w):
    r,t=run(w); row={"strategy":name}
    for p,(a,b) in periods.items():
        s=stats(r[a:b],t); row[f"{p} CAGR"]=s["CAGR"]; row[f"{p} DD"]=s["MaxDD"]
    s=stats(r[START:],t); row["Sharpe"]=s["Sharpe"]; row["Calmar"]=s["Calmar"]; row["Turn/yr"]=s["Turn_yr"]
    return row,r
rows=[]
r,_=report("BTC+ETH buy&hold 50/50",bh()); rows.append(r)
base,rb=report("TrendEnsemble volT40 (PRE-REGISTERED)",build()); rows.append(base)
for tv in [0.30,0.50,1.0]:
    r,_=report(f"  sens: volT={tv:.0%}" if tv<1 else "  sens: no vol target",build(tvol=tv)); rows.append(r)
for lb in [(50,),(100,),(50,100),(100,150,200)]:
    r,_=report(f"  sens: SMA{lb}",build(lookbacks=lb)); rows.append(r)
df=pd.DataFrame(rows).set_index("strategy")
print(df.round(2).to_string())
# paired bootstrap of Sharpe difference vs buy&hold
r_bh,_=run(bh()); r_st,_=run(build())
d=pd.concat([r_st[START:],r_bh[START:]],axis=1).dropna().values; T=len(d); k=int(np.ceil(T/20)); rng=np.random.default_rng(3)
sh=lambda x:x.mean()/x.std()*np.sqrt(365); diffs=[]; ddiff=[]
for _ in range(3000):
    st=rng.integers(0,T-20,k); s=np.concatenate([d[a:a+20] for a in st])[:T]; diffs.append(sh(s[:,0])-sh(s[:,1]))
print("Sharpe diff vs buy&hold 5/50/95%:",np.percentile(diffs,[5,50,95]).round(2)," P(>0)=",round((np.array(diffs)>0).mean(),2))
eq=(1+rb[START:]).cumprod(); print("worst drawdown strat:",round((eq/eq.cummax()-1).min(),3), " time-in-market(avg gross weight):",round(build()[SYMS].sum(axis=1)[START:].mean(),2))
