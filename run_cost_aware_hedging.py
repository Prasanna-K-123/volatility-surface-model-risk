"""Common-random-number GBM hedge-frequency/cost/volatility sensitivity study.

Controlled simulation at zero interest; not a market backtest or optimum policy
claim. Transaction costs include initial hedge and terminal liquidation.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from src.vol_surface.hedging import simulate_gbm_paths, bs_call_price_delta, delta_hedge_error

ROOT=Path(__file__).resolve().parent


def hedge_with_turnover(paths,K,T,sigma,every):
    if every<1 or int(every)!=every or np.any(paths<=0):
        raise ValueError('Positive prices and a positive integer rebalance interval required')
    steps=paths.shape[1]-1
    value, delta=bs_call_price_delta(paths[:,0],K,T,sigma)
    cash=value-delta*paths[:,0]
    turnover=abs(delta)*paths[:,0]
    for t in range(1,steps):
        if t%every: continue
        _,new_delta=bs_call_price_delta(paths[:,t],K,T*(1-t/steps),sigma)
        change=new_delta-delta
        turnover+=abs(change)*paths[:,t]
        cash-=change*paths[:,t]
        delta=new_delta
    turnover+=abs(delta)*paths[:,-1]
    gross=cash+delta*paths[:,-1]-np.maximum(paths[:,-1]-K,0)
    return gross,turnover


def main():
    S0,sigma,T,n=100.0,.55,30/365.25,3000
    paths=simulate_gbm_paths(S0,sigma,T,720,n,seed=20261009)
    rows=[]
    for hedge_sigma in [.45,.55,.65]:
        for every in [1,6,24]:
            gross,turnover=hedge_with_turnover(paths,S0,T,hedge_sigma,every)
            for bps in [0,1,5]:
                cost=turnover*bps/10000
                net=gross-cost
                se=np.std(net,ddof=1)/np.sqrt(n)/S0
                rows.append(dict(hedge_sigma=hedge_sigma,rebalance_every_hours=every,cost_bps_per_notional=bps,
                                 mean_net_pnl_over_spot=float(np.mean(net)/S0),
                                 mean_net_ci95_low=float(np.mean(net)/S0-1.96*se),
                                 mean_net_ci95_high=float(np.mean(net)/S0+1.96*se),
                                 rmse_net_over_spot=float(np.sqrt(np.mean(net**2))/S0),
                                 p95_abs_net_over_spot=float(np.quantile(abs(net),.95)/S0),
                                 mean_turnover_over_spot=float(np.mean(turnover)/S0),
                                 mean_cost_over_spot=float(np.mean(cost)/S0)))
    out=ROOT/'reference/cost_aware_hedging'
    out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'scenarios.csv',index=False)
    metadata=dict(paths=n,steps=720,seed=20261009,spot=S0,true_sigma=sigma,maturity_days=30,
                  model='GBM, zero rates, European ATM call; short option hedge PnL',
                  initial_and_terminal_costs=True,scenarios=len(rows),
                  limitations='Constant volatility and proportional costs; no spread dynamics, jumps, market impact or real executions.')
    (out/'protocol.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__': main()
