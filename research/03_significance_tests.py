from lib import *
from scipy.stats import norm
START="2019-01-01"
def W(sym,L):
    c=CLOSE[sym]; w=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns)
    w[sym]=(c>sma(c,L)).astype(float); return w
bh=pd.DataFrame(0.0,index=CLOSE.index,columns=CLOSE.columns); bh["BTCUSDT"]=1.0
rb,_=run(bh); rb=rb[START:]
def paired(ra,rb,n=3000,block=20,seed=1):
    d=pd.concat([ra,rb],axis=1).dropna().values; T=len(d); k=int(np.ceil(T/block)); rng=np.random.default_rng(seed)
    sh=lambda x:x.mean()/x.std()*np.sqrt(365)
    diffs=[];ddr=[]
    for _ in range(n):
        st=rng.integers(0,T-block,k); s=np.concatenate([d[a:a+block] for a in st])[:T]
        diffs.append(sh(s[:,0])-sh(s[:,1]))
    return np.percentile(diffs,[5,50,95]), (np.array(diffs)>0).mean()
for L in [50,100,150]:
    r,_=run(W("BTCUSDT",L)); r=r[START:]
    ci,p=paired(r,rb)
    print(f"BTC SMA{L} minus BTC buy&hold  Sharpe diff 5/50/95% = {ci.round(2)}  P(diff>0)={p:.2f}")
    print("   own Sharpe 5/50/95:",block_boot_sharpe(r).round(2))
# deflated sharpe (Bailey & Lopez de Prado) for the best of N trials
def dsr(r,N,sr_std):
    T=len(r); sr=r.mean()/r.std()  # daily
    g=0.5772; emax=(1-g)*norm.ppf(1-1/N)+g*norm.ppf(1-1/(N*np.e))
    sr0=emax*sr_std
    sk=r.skew(); ku=r.kurt()+3
    den=np.sqrt((1-sk*sr+(ku-1)/4*sr**2)/(T-1))
    return norm.cdf((sr-sr0)/den)
r,_=run(W("BTCUSDT",50)); r=r[START:]
trials_sr=[]
for sym in ["BTCUSDT","ETHUSDT"]:
    for L in [20,50,100,150,200]:
        rr,_=run(W(sym,L)); rr=rr[START:]; trials_sr.append(rr.mean()/rr.std())
print("trials so far (this sheet only):",len(trials_sr)," std of daily SR across trials:",np.std(trials_sr).round(4))
for N in [10,30,60]:
    print(f"Deflated Sharpe prob that BTC SMA50 is real, assuming {N} total trials tried: {dsr(r,N,np.std(trials_sr)):.2f}")
