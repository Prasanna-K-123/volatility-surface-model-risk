from __future__ import annotations

from dataclasses import asdict
import numpy as np
import pandas as pd
from scipy.stats import norm

from .svi import SVIParams, svi_total_variance


def black76_normalized_call(k: np.ndarray, sigma: np.ndarray, T: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    root = sigma * np.sqrt(T)
    d1 = -k / root + 0.5 * root
    d2 = d1 - root
    return norm.cdf(d1) - np.exp(k) * norm.cdf(d2)


def static_arbitrage_diagnostics(p: SVIParams, T: float, forward: float, k_min: float, k_max: float) -> dict:
    grid = np.linspace(k_min, k_max, 401)
    w = svi_total_variance(grid, p)
    sigma = np.sqrt(np.maximum(w, 1e-12) / T)
    strikes = forward * np.exp(grid)
    calls = forward * black76_normalized_call(grid, sigma, T)
    d1 = np.gradient(calls, strikes)
    d2 = np.gradient(d1, strikes)
    return {
        "negative_total_variance_points": int(np.sum(w <= 0)),
        "call_monotonicity_violations": int(np.sum(d1 > 1e-8)),
        "call_convexity_violations": int(np.sum(d2 < -1e-8)),
        "min_total_variance": float(w.min()),
        "min_call_second_derivative": float(d2.min()),
    }


def calendar_arbitrage_diagnostics(fits: list[dict], k_lo: float = -0.3, k_hi: float = 0.3) -> pd.DataFrame:
    grid = np.linspace(k_lo, k_hi, 121)
    ordered = sorted(fits, key=lambda x: x["T"])
    rows = []
    for left, right in zip(ordered[:-1], ordered[1:]):
        wl = svi_total_variance(grid, left["params"])
        wr = svi_total_variance(grid, right["params"])
        diff = wr - wl
        rows.append(
            {
                "near_expiry": left["expiry"],
                "far_expiry": right["expiry"],
                "near_T": left["T"],
                "far_T": right["T"],
                "violating_grid_points": int(np.sum(diff < -1e-6)),
                "min_total_variance_increment": float(diff.min()),
            }
        )
    return pd.DataFrame(rows)


def fit_summary_row(expiry: str, fit: dict, static_diag: dict) -> dict:
    row = {
        "expiry": expiry,
        "T": fit["T"],
        "forward": fit["forward"],
        "n_strikes": fit["n_strikes"],
        "holdout_rmse_total_variance": fit["holdout_rmse_total_variance"],
        "quadratic_holdout_rmse_total_variance": fit["quadratic_holdout_rmse_total_variance"],
        "svi_minus_quadratic_holdout_rmse": fit["svi_minus_quadratic_holdout_rmse"],
        "svi_beats_quadratic_holdout": fit["svi_beats_quadratic_holdout"],
        "full_rmse_total_variance": fit["full_rmse_total_variance"],
        "observed_k_min": fit["observed_k_min"],
        "observed_k_max": fit["observed_k_max"],
        "analytic_min_total_variance": fit["analytic_min_total_variance"],
        "left_wing_slope": fit["left_wing_slope"],
        "right_wing_slope": fit["right_wing_slope"],
        "svi_m_outside_observed_range": fit["svi_m_outside_observed_range"],
        "svi_sigma_to_observed_k_span": fit["svi_sigma_to_observed_k_span"],
    }
    row.update({f"svi_{k}": v for k, v in asdict(fit["params"]).items()})
    row.update(static_diag)
    return row
