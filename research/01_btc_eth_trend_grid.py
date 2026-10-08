from lib import *
pd.set_option("display.width",200)
START="2019-01-01"
rows=[]
for sym in ["BTCUSDT","ETHUSDT"]:
    c=CLOSE[sym]
    w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns); w[sym]=1.0
    r,t=run(w); r=r[START:]; rows.append((sym,"buy&hold",stats(r,t)))
    for L in [20,50,100,150,200]:
        w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns)
        w[sym]=(c>sma(c,L)).astype(float).where(sma(c,L).notna(),0.0)
        r,t=run(w); rows.append((sym,f"SMA{L}",stats(r[START:],t)))
    # vol-target overlay on SMA100
    for L in [100]:
        sig=(c>sma(c,L)).astype(float)
        sc=(0.40/rvol(20)[sym]).clip(upper=1.0)
        w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns); w[sym]=(sig*sc).fillna(0)
        r,t=run(w); rows.append((sym,f"SMA{L}+volT40",stats(r[START:],t)))
out=pd.DataFrame([dict(asset=a,strat=s,**m) for a,s,m in rows]).set_index(["asset","strat"])
print(out.round(3).to_string())
