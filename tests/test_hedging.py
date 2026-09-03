import numpy as np

from vol_surface.hedging import simulate_gbm_paths, delta_hedge_error, hedging_experiment


def test_hedging_is_deterministic_and_finite():
    paths1 = simulate_gbm_paths(100, 0.5, 30/365.25, 120, 500, seed=42)
    paths2 = simulate_gbm_paths(100, 0.5, 30/365.25, 120, 500, seed=42)
    assert np.allclose(paths1, paths2)
    err = delta_hedge_error(paths1, 100, 30/365.25, 0.5, 1)
    assert np.isfinite(err).all()
    assert np.mean(np.abs(err)) < 5.0


def test_hedging_experiment_reports_model_risk():
    out = hedging_experiment(100, 0.6, paths=600, steps_per_day=12)
    assert len(out) == 5
    assert (out["p95_abs_error_pct_spot"] >= 0).all()
