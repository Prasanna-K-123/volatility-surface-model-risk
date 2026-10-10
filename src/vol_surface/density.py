"""Analytic raw-SVI density diagnostics and an observed-support evaluation guard.

Gatheral & Jacquier, arXiv:1204.0646, equation (2.1), give the density-sign
factor g. Positivity of total variance and sub-2 wing slopes do not by
themselves establish g >= 0. Sampling g is a diagnostic, not a global proof.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .svi import SVIParams, svi_analytic_minimum, svi_total_variance


def _validate_params(p: SVIParams) -> None:
    if not np.isfinite([p.a, p.b, p.rho, p.m, p.sigma]).all():
        raise ValueError("SVI parameters must be finite")
    if p.b < 0 or p.sigma <= 0 or abs(p.rho) >= 1:
        raise ValueError("Require b >= 0, sigma > 0 and |rho| < 1")
    if svi_analytic_minimum(p) <= 0:
        raise ValueError("Total variance must have a strictly positive analytic minimum")


def _finite_k(k: np.ndarray) -> np.ndarray:
    values = np.asarray(k, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Log-moneyness must be finite")
    return values


def svi_density_factor(k: np.ndarray, p: SVIParams) -> np.ndarray:
    """Evaluate g(k), whose sign is the sign of the implied call density.

    The analytic derivative calculation is valid wherever w > 0. A positive
    result at supplied points does not certify positivity between them or in
    the wings. This function intentionally permits explicit diagnostic stress
    points; normal observed-support evaluation uses SupportedSVISlice instead.
    """
    _validate_params(p)
    values = _finite_k(k)
    x = values - p.m
    radius = np.hypot(x, p.sigma)
    w = svi_total_variance(values, p)
    wp = p.b * (p.rho + x / radius)
    wpp = p.b * p.sigma**2 / radius**3
    with np.errstate(over="raise", divide="raise", invalid="raise"):
        try:
            g = (1.0 - values * wp / (2.0 * w))**2
            g -= wp**2 / 4.0 * (1.0 / w + 0.25)
            g += wpp / 2.0
        except FloatingPointError as exc:
            raise ValueError("Numerically unsupported density calculation") from exc
    if not np.isfinite(g).all():
        raise ValueError("Non-finite density factor")
    return g


@dataclass(frozen=True)
class SupportedSVISlice:
    """An explicit contract that rejects evaluation outside observed support.

    This guard limits extrapolation; it neither changes the fit nor proves
    continuous or global absence of arbitrage. Raw SVI remains available for
    research stress tests through explicitly unguarded diagnostic functions.
    """
    params: SVIParams
    k_min: float
    k_max: float

    def __post_init__(self) -> None:
        _validate_params(self.params)
        if not np.isfinite([self.k_min, self.k_max]).all() or self.k_min >= self.k_max:
            raise ValueError("Observed support must have finite, increasing bounds")

    def total_variance(self, k: np.ndarray) -> np.ndarray:
        values = _finite_k(k)
        if np.any(values < self.k_min) or np.any(values > self.k_max):
            raise ValueError("Unsupported SVI extrapolation outside observed strike support")
        return svi_total_variance(values, self.params)

