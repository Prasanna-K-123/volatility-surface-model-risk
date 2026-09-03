from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import least_squares


@dataclass(frozen=True)
class SVIParams:
    a: float
    b: float
    rho: float
    m: float
    sigma: float


def svi_total_variance(k: np.ndarray, p: SVIParams) -> np.ndarray:
    x = np.asarray(k, dtype=float) - p.m
    return p.a + p.b * (p.rho * x + np.sqrt(x * x + p.sigma * p.sigma))


def svi_analytic_minimum(p: SVIParams) -> float:
    """Analytic minimum of raw-SVI total variance over log-moneyness."""
    return float(p.a + p.b * p.sigma * np.sqrt(max(0.0, 1.0 - p.rho * p.rho)))


def svi_wing_slopes(p: SVIParams) -> tuple[float, float]:
    """Asymptotic total-variance slopes in the left and right wings."""
    return float(p.b * (1.0 - p.rho)), float(p.b * (1.0 + p.rho))


def _sigmoid(x: float) -> float:
    if x >= 0:
        e = np.exp(-x)
        return float(1.0 / (1.0 + e))
    e = np.exp(x)
    return float(e / (1.0 + e))


def _params_from_transformed(z: np.ndarray) -> SVIParams:
    """
    Map optimization variables to a structurally constrained raw-SVI parameter set.

    Construction guarantees b>0, |rho|<0.999, sigma>0, positive analytic minimum
    total variance, and both Lee-style asymptotic total-variance slopes below 2.
    """
    rho = 0.999 * np.tanh(float(z[1]))
    max_b = 1.999 / (1.0 + abs(rho))
    b = max_b * _sigmoid(float(z[0]))
    m = float(z[2])
    sigma = float(np.exp(z[3]))
    minimum_variance = float(np.exp(z[4]))
    a = minimum_variance - b * sigma * np.sqrt(max(0.0, 1.0 - rho * rho))
    return SVIParams(a=a, b=b, rho=rho, m=m, sigma=sigma)


def fit_svi(k: np.ndarray, total_variance: np.ndarray) -> SVIParams:
    k = np.asarray(k, dtype=float)
    w = np.asarray(total_variance, dtype=float)
    if len(k) < 5:
        raise ValueError("SVI requires at least five points")
    if not np.isfinite(k).all() or not np.isfinite(w).all() or np.any(w <= 0):
        raise ValueError("Finite positive total variance required")

    order = np.argsort(np.abs(k))[: max(1, min(3, len(w)))]
    atm = float(np.median(w[order]))
    min_w = float(np.min(w))
    k_med = float(np.median(k))
    scale = max(1e-7, atm)

    # Transformed coordinates: [wing-scale, skew, center, log(sigma), log(minimum variance)].
    # Broad numerical bounds remain only to keep the optimizer in a finite search region;
    # economic positivity and wing-slope conditions are guaranteed by the transformation.
    m_lo = float(k.min()) - 1.0
    m_hi = float(k.max()) + 1.0
    lb = np.array([-12.0, -5.0, m_lo, np.log(1e-4), np.log(1e-8)])
    ub = np.array([12.0, 5.0, m_hi, np.log(5.0), np.log(max(2.0, 20.0 * float(np.max(w))))])

    def residual(z: np.ndarray) -> np.ndarray:
        p = _params_from_transformed(z)
        return (svi_total_variance(k, p) - w) / scale

    seeds = [
        np.array([-2.5, -0.25, 0.0, np.log(0.20), np.log(max(1e-7, 0.5 * min_w))]),
        np.array([-3.5, 0.0, k_med, np.log(0.50), np.log(max(1e-7, 0.8 * min_w))]),
        np.array([-1.5, -0.50, k_med, np.log(1.00), np.log(max(1e-7, 0.3 * min_w))]),
        np.array([-4.0, 0.35, k_med, np.log(0.10), np.log(max(1e-7, 0.9 * min_w))]),
    ]

    best = None
    best_cost = np.inf
    for seed in seeds:
        seed = np.clip(seed, lb + 1e-10, ub - 1e-10)
        res = least_squares(
            residual,
            seed,
            bounds=(lb, ub),
            max_nfev=30000,
            xtol=1e-12,
            ftol=1e-12,
            gtol=1e-12,
            x_scale="jac",
        )
        if res.success and np.isfinite(res.cost) and res.cost < best_cost:
            best, best_cost = res.x, float(res.cost)

    if best is None:
        raise RuntimeError("SVI calibration failed")

    p = _params_from_transformed(best)
    minimum = svi_analytic_minimum(p)
    left_slope, right_slope = svi_wing_slopes(p)
    if not (minimum > 0.0 and 0.0 <= left_slope < 2.0 and 0.0 <= right_slope < 2.0):
        raise RuntimeError("SVI structural constraints violated after calibration")
    return p


def alternating_strike_holdout(expiry_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    strikes = np.array(sorted(expiry_df["strike"].unique()))
    fit_strikes = set(strikes[::2])
    return expiry_df[expiry_df["strike"].isin(fit_strikes)].copy(), expiry_df[~expiry_df["strike"].isin(fit_strikes)].copy()


def quadratic_holdout_rmse(train: pd.DataFrame, test: pd.DataFrame) -> float:
    """Simple cross-sectional total-variance baseline fitted only on holdout-training strikes."""
    coef = np.polyfit(train["k"].to_numpy(dtype=float), train["total_variance"].to_numpy(dtype=float), deg=2)
    pred = np.polyval(coef, test["k"].to_numpy(dtype=float))
    y = test["total_variance"].to_numpy(dtype=float)
    return float(np.sqrt(np.mean((pred - y) ** 2)))


def evaluate_expiry(expiry_df: pd.DataFrame) -> dict:
    curve = (
        expiry_df.groupby("strike", as_index=False)
        .agg(
            k=("k", "mean"),
            total_variance=("total_variance", "mean"),
            iv=("iv", "mean"),
            T=("T", "mean"),
            forward=("forward", "median"),
        )
        .sort_values("strike")
    )
    if len(curve) < 10:
        raise ValueError("Need at least ten strikes for an expiry")
    train, test = alternating_strike_holdout(curve)
    if len(train) < 5 or len(test) < 3:
        raise ValueError("Insufficient alternating-strike holdout")

    p_holdout = fit_svi(train["k"].to_numpy(), train["total_variance"].to_numpy())
    test_pred = svi_total_variance(test["k"].to_numpy(), p_holdout)
    y_test = test["total_variance"].to_numpy(dtype=float)
    holdout_rmse = float(np.sqrt(np.mean((test_pred - y_test) ** 2)))
    baseline_rmse = quadratic_holdout_rmse(train, test)

    p_full = fit_svi(curve["k"].to_numpy(), curve["total_variance"].to_numpy())
    full_pred = svi_total_variance(curve["k"].to_numpy(), p_full)
    full_rmse = float(np.sqrt(np.mean((full_pred - curve["total_variance"].to_numpy()) ** 2)))
    left_slope, right_slope = svi_wing_slopes(p_full)
    k_min = float(curve["k"].min())
    k_max = float(curve["k"].max())
    k_span = max(1e-12, k_max - k_min)

    return {
        "params": p_full,
        "curve": curve,
        "holdout_rmse_total_variance": holdout_rmse,
        "quadratic_holdout_rmse_total_variance": baseline_rmse,
        "svi_minus_quadratic_holdout_rmse": holdout_rmse - baseline_rmse,
        "svi_beats_quadratic_holdout": bool(holdout_rmse < baseline_rmse),
        "full_rmse_total_variance": full_rmse,
        "n_strikes": int(len(curve)),
        "T": float(curve["T"].median()),
        "forward": float(curve["forward"].median()),
        "observed_k_min": k_min,
        "observed_k_max": k_max,
        "analytic_min_total_variance": svi_analytic_minimum(p_full),
        "left_wing_slope": left_slope,
        "right_wing_slope": right_slope,
        "svi_m_outside_observed_range": bool(p_full.m < k_min or p_full.m > k_max),
        "svi_sigma_to_observed_k_span": float(p_full.sigma / k_span),
    }
