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
