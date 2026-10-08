exec(open("09_fx_carry.py").read().split("for mk in")[0])
idx=ret.index
mend=pd.Series(idx,index=idx).groupby([idx.year,idx.month]).max().values
w=pd.DataFrame(np.nan,index=idx,columns=ret.columns)
for dt in mend:
    if dt<pd.Timestamp("2002-06-01"): continue
    rt=rd.loc[dt,ret.columns].dropna(); row=pd.Series(0.0,index=ret.columns)
    o=rt.sort_values(); row[o.index[-2:]]=0.5; row[o.index[:2]]=-0.5; w.loc[dt]=row
w=w.ffill().fillna(0.0); held=w.shift(2)["2002-06":]
spot=(held*ret["2002-06":]).sum(axis=1); car=(held*carry_d["2002-06":]).sum(axis=1)
for name,a,b in [("2002-06..2007","2002-06","2007-12"),("2008-2009","2008","2009"),("2010-2019","2010","2019"),("2020-2026","2020","2026"),("ALL","2002-06","2026")]:
    s,c=spot[a:b],car[a:b]; y=len(s)/252
    print(f"{name:14s} carry {c.sum()/y:6.2%}/yr   spot {s.sum()/y:6.2%}/yr   total {(c+s).sum()/y:6.2%}/yr   vol {(c+s).std()*252**.5:5.1%}")
print("avg long legs:",held.clip(lower=0).gt(0).sum(axis=0).div(len(held)).round(2).to_dict())
print("avg short legs:",held.clip(upper=0).lt(0).sum(axis=0).div(len(held)).round(2).to_dict())
