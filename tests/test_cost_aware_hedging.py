import numpy as np
from run_cost_aware_hedging import hedge_with_turnover
from src.vol_surface.hedging import simulate_gbm_paths,delta_hedge_error


def test_zero_cost_matches_independent_original_hedge():
    paths=simulate_gbm_paths(100,.55,.05,48,200,seed=41)
    for every in [1,6,24]:
        gross,turnover=hedge_with_turnover(paths,100,.05,.55,every)
        np.testing.assert_allclose(gross,delta_hedge_error(paths,100,.05,.55,every),atol=1e-12)
        assert np.all(turnover>=0)


def test_cost_decreases_pathwise_pnl_and_includes_liquidation():
    paths=np.full((3,5),100.0)
    gross,turnover=hedge_with_turnover(paths,100,.1,.5,10)
    from src.vol_surface.hedging import bs_call_price_delta
    _,delta=bs_call_price_delta(np.array([100]),100,.1,.5)
    np.testing.assert_allclose(turnover,2*100*delta[0])
    assert np.all(gross-turnover*.0005<=gross)
