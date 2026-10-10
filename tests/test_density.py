import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from scipy.stats import norm

from vol_surface.density import SupportedSVISlice, svi_density_factor
from vol_surface.svi import SVIParams, svi_analytic_minimum, svi_total_variance, svi_wing_slopes


def test_constant_variance_density_factor_is_one():
    p = SVIParams(a=0.04, b=0.0, rho=0.0, m=0.0, sigma=0.2)
    np.testing.assert_array_equal(svi_density_factor(np.array([-3.0, 0.0, 3.0]), p), 1.0)


def test_density_sign_and_magnitude_agree_with_independent_call_differentiation():
    p = SVIParams(a=0.04, b=0.08, rho=-0.25, m=0.0, sigma=0.2)
    strikes = np.exp(np.array([-0.2, 0.0, 0.2]))

    def call(x):
        k = np.log(x)
        w = svi_total_variance(k, p)
        root = np.sqrt(w)
        return norm.cdf(-k / root + root / 2) - x * norm.cdf(-k / root - root / 2)

    # Five-point numerical differentiation of option prices with respect to
    # strike, independent of the implementation's analytic SVI derivatives.
    h = 2e-4 * strikes
    numerical = (-call(strikes + 2*h) + 16*call(strikes + h) - 30*call(strikes)
                 + 16*call(strikes - h) - call(strikes - 2*h)) / (12*h*h)
    k = np.log(strikes)
    w = svi_total_variance(k, p)
    dminus = -k / np.sqrt(w) - np.sqrt(w) / 2
    analytic = svi_density_factor(k, p) * norm.pdf(dminus) / (strikes * np.sqrt(w))
    np.testing.assert_allclose(analytic, numerical, rtol=2e-6, atol=1e-7)


def test_structural_constraints_do_not_rule_out_negative_density():
    frame = pd.read_csv(Path(__file__).resolve().parents[1] / "reference/svi_fit_summary.csv")
    row = frame.iloc[1]
    p = SVIParams(**{key: float(row["svi_" + key]) for key in ["a", "b", "rho", "m", "sigma"]})
    assert svi_analytic_minimum(p) > 0
    assert max(svi_wing_slopes(p)) < 2
    assert svi_density_factor(np.array([-3.0]), p)[0] < -0.05
    observed = SupportedSVISlice(p, float(row.observed_k_min), float(row.observed_k_max))
    with pytest.raises(ValueError, match="extrapolation"):
        observed.total_variance(np.array([-3.0]))


def test_support_guard_accepts_endpoints_and_rejects_one_outside_element():
    p = SVIParams(a=0.04, b=0.08, rho=-0.25, m=0.0, sigma=0.2)
    supported = SupportedSVISlice(p, -0.2, 0.3)
    k = np.array([-0.2, 0.0, 0.3])
    np.testing.assert_array_equal(supported.total_variance(k), svi_total_variance(k, p))
    with pytest.raises(ValueError, match="extrapolation"):
        supported.total_variance(np.array([0.0, 0.30000001]))
    with pytest.raises(ValueError, match="finite"):
        supported.total_variance(np.array([np.nan]))


@pytest.mark.parametrize("p", [
    SVIParams(a=0.0, b=0.0, rho=0.0, m=0.0, sigma=0.2),
    SVIParams(a=0.1, b=-0.1, rho=0.0, m=0.0, sigma=0.2),
    SVIParams(a=0.1, b=0.1, rho=1.0, m=0.0, sigma=0.2),
    SVIParams(a=0.1, b=0.1, rho=0.0, m=0.0, sigma=0.0),
    SVIParams(a=np.nan, b=0.1, rho=0.0, m=0.0, sigma=0.2),
])
def test_invalid_parameters_are_rejected(p):
    with pytest.raises(ValueError):
        svi_density_factor(np.array([0.0]), p)


@pytest.mark.parametrize("lo,hi", [(0.1, 0.1), (0.2, -0.2), (np.nan, 0.2)])
def test_invalid_support_is_rejected(lo, hi):
    p = SVIParams(a=0.04, b=0.0, rho=0.0, m=0.0, sigma=0.2)
    with pytest.raises(ValueError):
        SupportedSVISlice(p, lo, hi)
