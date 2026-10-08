import lib
from lib import *
import daily_trend_model as f
START="2018-04-01"
for cost in [0.001,0.0015,0.003]:
    lib.COST=cost
    r,t=run(f.build(),cost=cost); r=r[START:]
    eq=(1+r).cumprod(); yrs=len(r)/365
    print(f"cost/side {cost:.2%}: CAGR {eq.iloc[-1]**(1/yrs)-1:6.1%}  final x{eq.iloc[-1]:5.1f}  Sharpe {r.mean()/r.std()*365**.5:4.2f}  MTM maxDD {(eq/eq.cummax()-1).min():6.1%}")
rb,_=run(f.bh()); rb=rb[START:]; eq=(1+rb).cumprod(); yrs=len(rb)/365
print(f"B&H 50/50  : CAGR {eq.iloc[-1]**(1/yrs)-1:6.1%}  final x{eq.iloc[-1]:5.1f}  MTM maxDD {(eq/eq.cummax()-1).min():6.1%}")
