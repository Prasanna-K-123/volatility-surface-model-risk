import numpy as np
import pandas as pd

from vol_surface.svi import (
    SVIParams,
    evaluate_expiry,
    fit_svi,
    svi_analytic_minimum,
    svi_total_variance,
    svi_wing_slopes,
)
from vol_surface.diagnostics import static_arbitrage_diagnostics


def test_svi_recovers_smooth_surface():
    k = np.linspace(-0.35, 0.35, 31)
    true = SVIParams(a=0.035, b=0.11, rho=-0.35, m=0.02, sigma=0.18)
    w = svi_total_variance(k, true)
    fit = fit_svi(k, w)
    pred = svi_total_variance(k, fit)
    assert np.sqrt(np.mean((pred - w) ** 2)) < 1e-5
    assert np.min(pred) > 0
    assert svi_analytic_minimum(fit) > 0
    left, right = svi_wing_slopes(fit)
    assert 0 <= left < 2
    assert 0 <= right < 2


def test_expiry_holdout_baseline_and_static_shape():
    k = np.linspace(-0.3, 0.3, 25)
    p = SVIParams(a=0.04, b=0.08, rho=-0.25, m=0.0, sigma=0.2)
    T = 0.25
    w = svi_total_variance(k, p)
    df = pd.DataFrame(
        {
            "strike": 100 * np.exp(k),
            "k": k,
            "total_variance": w,
            "iv": np.sqrt(w / T),
            "T": T,
            "forward": 100.0,
        }
    )
    fit = evaluate_expiry(df)
    assert fit["holdout_rmse_total_variance"] < 5e-4
    assert fit["quadratic_holdout_rmse_total_variance"] > 0
    assert fit["svi_beats_quadratic_holdout"]
    assert fit["svi_minus_quadratic_holdout_rmse"] < 0
    assert fit["analytic_min_total_variance"] > 0
    assert fit["left_wing_slope"] < 2
    assert fit["right_wing_slope"] < 2
    assert fit["svi_sigma_to_observed_k_span"] > 0
    diag = static_arbitrage_diagnostics(fit["params"], T, 100.0, -0.3, 0.3)
    assert diag["negative_total_variance_points"] == 0
    assert diag["call_monotonicity_violations"] == 0
    assert diag["call_convexity_violations"] == 0
