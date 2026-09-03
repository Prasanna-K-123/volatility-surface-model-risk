from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def bs_call_price_delta(S: np.ndarray, K: float, tau: float, sigma: float, r: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    S = np.asarray(S, dtype=float)
    if tau <= 0:
        payoff = np.maximum(S - K, 0.0)
        return payoff, (S > K).astype(float)
    root = sigma * np.sqrt(tau)
    d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * tau) / root
    d2 = d1 - root
    price = S * norm.cdf(d1) - K * np.exp(-r * tau) * norm.cdf(d2)
    return price, norm.cdf(d1)


def simulate_gbm_paths(S0: float, sigma: float, T: float, steps: int, paths: int, seed: int = 2027) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dt = T / steps
    z = rng.standard_normal((paths, steps))
    inc = (-0.5 * sigma * sigma * dt) + sigma * np.sqrt(dt) * z
    log_paths = np.cumsum(inc, axis=1)
    out = np.empty((paths, steps + 1), dtype=float)
    out[:, 0] = S0
    out[:, 1:] = S0 * np.exp(log_paths)
    return out


def delta_hedge_error(paths: np.ndarray, K: float, T: float, hedge_sigma: float, rebalance_every: int = 1) -> np.ndarray:
    n_paths, n_cols = paths.shape
    steps = n_cols - 1
    dt = T / steps
    initial_price, initial_delta = bs_call_price_delta(paths[:, 0], K, T, hedge_sigma)
    cash = initial_price - initial_delta * paths[:, 0]
    delta = initial_delta.copy()
    for t in range(1, steps):
        if t % rebalance_every != 0:
            continue
        tau = T - t * dt
        _, new_delta = bs_call_price_delta(paths[:, t], K, tau, hedge_sigma)
        cash -= (new_delta - delta) * paths[:, t]
        delta = new_delta
    terminal_portfolio = cash + delta * paths[:, -1]
    payoff = np.maximum(paths[:, -1] - K, 0.0)
    return terminal_portfolio - payoff


def hedging_experiment(S0: float, true_sigma: float, T: float = 30 / 365.25, paths: int = 4000, steps_per_day: int = 24) -> pd.DataFrame:
    steps = max(24, int(round(T * 365.25 * steps_per_day)))
    simulated = simulate_gbm_paths(S0, true_sigma, T, steps=steps, paths=paths)
    scenarios = [
        ("hourly_correct_vol", true_sigma, 1),
        ("6h_correct_vol", true_sigma, 6),
        ("daily_correct_vol", true_sigma, 24),
        ("hourly_vol_minus_10pt", max(0.05, true_sigma - 0.10), 1),
        ("hourly_vol_plus_10pt", true_sigma + 0.10, 1),
    ]
    records = []
    for name, vol, every in scenarios:
        err = delta_hedge_error(simulated, K=S0, T=T, hedge_sigma=vol, rebalance_every=every)
        records.append({
            "scenario": name,
            "hedge_sigma": vol,
            "rebalance_every_hours": every,
            "mean_error_pct_spot": float(np.mean(err) / S0),
            "mean_abs_error_pct_spot": float(np.mean(np.abs(err)) / S0),
            "p95_abs_error_pct_spot": float(np.quantile(np.abs(err), 0.95) / S0),
            "p99_abs_error_pct_spot": float(np.quantile(np.abs(err), 0.99) / S0),
        })
    return pd.DataFrame(records)
