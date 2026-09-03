from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from vol_surface.data import clean_surface_universe
from vol_surface.diagnostics import (
    calendar_arbitrage_diagnostics,
    fit_summary_row,
    static_arbitrage_diagnostics,
)
from vol_surface.hedging import hedging_experiment
from vol_surface.svi import evaluate_expiry


def _assert_close(actual: float, expected: float, label: str, *, atol: float = 5e-8, rtol: float = 5e-4) -> None:
    if not math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=rtol):
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_series_close(actual: pd.Series, expected: pd.Series, label: str, *, atol: float = 5e-8, rtol: float = 2e-3) -> None:
    left = pd.to_numeric(actual, errors="coerce").to_numpy(dtype=float)
    right = pd.to_numeric(expected, errors="coerce").to_numpy(dtype=float)
    if not np.allclose(left, right, rtol=rtol, atol=atol, equal_nan=True):
        diff = np.nanmax(np.abs(left - right))
        raise AssertionError(f"{label}: maximum absolute difference {diff}")


def main() -> None:
    root = Path(__file__).resolve().parent
    reference = root / "reference"
    output = root / "results" / "reference_reproduction"
    output.mkdir(parents=True, exist_ok=True)

    expected_summary = json.loads((reference / "research_summary.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(reference / "accepted_snapshot_inputs.csv.gz", compression="gzip")
    required_raw = {
        "expiration_timestamp", "strike", "option_type", "mark_iv", "underlying_price",
        "open_interest", "bid_price", "ask_price", "captured_at_utc",
    }
    missing = required_raw.difference(raw.columns)
    if missing:
        raise AssertionError(f"reference snapshot input is missing columns: {sorted(missing)}")
    if len(raw) != 978:
        raise AssertionError(f"reference snapshot must contain 978 option rows, got {len(raw)}")

    captured = str(expected_summary["snapshot"]["captured_at_utc"])
    if set(raw["captured_at_utc"].astype(str)) != {captured}:
        raise AssertionError("reference snapshot capture timestamp does not match accepted metadata")

    universe = clean_surface_universe(raw, captured)
    if len(universe) != 466:
        raise AssertionError(f"accepted cleaning pipeline must produce 466 rows, got {len(universe)}")

    fits: list[dict] = []
    summary_rows: list[dict] = []
    for expiry, part in universe.groupby("expiry"):
        try:
            fit = evaluate_expiry(part)
        except ValueError:
            continue
        fit["expiry"] = pd.Timestamp(expiry).isoformat()
        curve = fit["curve"]
        diag = static_arbitrage_diagnostics(
            fit["params"],
            fit["T"],
            fit["forward"],
            float(curve["k"].min()),
            float(curve["k"].max()),
        )
        fits.append(fit)
        summary_rows.append(fit_summary_row(fit["expiry"], fit, diag))

    fit_summary = pd.DataFrame(summary_rows).sort_values("T").reset_index(drop=True)
    if len(fit_summary) != 6:
        raise AssertionError(f"reference reproduction must produce 6 fitted expiries, got {len(fit_summary)}")

    calendar = calendar_arbitrage_diagnostics(fits).reset_index(drop=True)
    atm_idx = int(np.argmin(np.abs(universe["k"].to_numpy())))
    atm_iv = float(universe.iloc[atm_idx]["iv"])
    spot_proxy = float(universe.iloc[atm_idx]["forward"])
    hedging = hedging_experiment(S0=spot_proxy, true_sigma=atm_iv).reset_index(drop=True)

    expected_fit = pd.read_csv(reference / "svi_fit_summary.csv")
    expected_calendar = pd.read_csv(reference / "calendar_arbitrage_diagnostics.csv")
    expected_hedging = pd.read_csv(reference / "delta_hedging_model_risk.csv")

    exact_values = {
        "clean_option_rows": len(universe),
        "fitted_expiries": len(fit_summary),
        "svi_holdout_wins_vs_quadratic": int(fit_summary["svi_beats_quadratic_holdout"].sum()),
        "expiries_with_svi_m_outside_observed_range": int(fit_summary["svi_m_outside_observed_range"].sum()),
        "total_static_convexity_violations": int(fit_summary["call_convexity_violations"].sum()),
        "calendar_violating_grid_points": int(calendar["violating_grid_points"].sum()) if len(calendar) else 0,
    }
    for key, actual in exact_values.items():
        expected = int(expected_summary[key])
        if int(actual) != expected:
            raise AssertionError(f"{key}: expected {expected}, got {actual}")

    _assert_close(
        fit_summary["holdout_rmse_total_variance"].median(),
        expected_summary["median_svi_holdout_rmse_total_variance"],
        "median SVI holdout RMSE",
    )
    _assert_close(
        fit_summary["quadratic_holdout_rmse_total_variance"].median(),
        expected_summary["median_quadratic_holdout_rmse_total_variance"],
        "median quadratic holdout RMSE",
    )
    _assert_close(atm_iv, expected_summary["atm_iv_used_for_simulated_hedging"], "ATM IV", atol=1e-12, rtol=1e-12)

    if fit_summary["expiry"].astype(str).tolist() != expected_fit["expiry"].astype(str).tolist():
        raise AssertionError("fitted expiry identity changed")

    # Gate the numerically stable, recruiter-facing curve evidence against the
    # accepted tables. Raw-SVI extrapolation parameters can move across BLAS/CPU
    # environments on weakly identified slices without materially changing the
    # observed-support curve or held-out errors.
    for column in [
        "T", "forward", "n_strikes", "holdout_rmse_total_variance",
        "quadratic_holdout_rmse_total_variance", "full_rmse_total_variance",
        "observed_k_min", "observed_k_max", "min_total_variance",
        "min_call_second_derivative",
    ]:
        _assert_series_close(fit_summary[column], expected_fit[column], f"SVI diagnostic {column}")

    # Structural raw-SVI constraints are properties to satisfy, not parameters
    # to reproduce digit-for-digit. This preserves the scientific claim while
    # avoiding a false reproducibility requirement on weakly identified fits.
    analytic_min = pd.to_numeric(fit_summary["analytic_min_total_variance"], errors="coerce").to_numpy(dtype=float)
    left_slope = pd.to_numeric(fit_summary["left_wing_slope"], errors="coerce").to_numpy(dtype=float)
    right_slope = pd.to_numeric(fit_summary["right_wing_slope"], errors="coerce").to_numpy(dtype=float)
    sigma_span = pd.to_numeric(fit_summary["svi_sigma_to_observed_k_span"], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(analytic_min) & (analytic_min > 0.0)):
        raise AssertionError("SVI analytic minimum total variance must remain positive")
    if not np.all(np.isfinite(left_slope) & (left_slope >= 0.0) & (left_slope < 2.0)):
        raise AssertionError("SVI left wing slopes must remain in [0, 2)")
    if not np.all(np.isfinite(right_slope) & (right_slope >= 0.0) & (right_slope < 2.0)):
        raise AssertionError("SVI right wing slopes must remain in [0, 2)")
    if not np.all(np.isfinite(sigma_span) & (sigma_span > 0.0)):
        raise AssertionError("SVI sigma/support-span diagnostics must remain finite and positive")

    for column in [
        "svi_beats_quadratic_holdout", "svi_m_outside_observed_range",
        "negative_total_variance_points", "call_monotonicity_violations",
        "call_convexity_violations",
    ]:
        if fit_summary[column].astype(str).tolist() != expected_fit[column].astype(str).tolist():
            raise AssertionError(f"SVI diagnostic {column} changed")

    if calendar[["near_expiry", "far_expiry", "violating_grid_points"]].astype(str).values.tolist() != expected_calendar[["near_expiry", "far_expiry", "violating_grid_points"]].astype(str).values.tolist():
        raise AssertionError("calendar-arbitrage identity/count diagnostics changed")
    for column in ["near_T", "far_T", "min_total_variance_increment"]:
        _assert_series_close(calendar[column], expected_calendar[column], f"calendar diagnostic {column}")

    if hedging["scenario"].astype(str).tolist() != expected_hedging["scenario"].astype(str).tolist():
        raise AssertionError("hedging scenario identity changed")
    for column in [
        "hedge_sigma", "rebalance_every_hours", "mean_error_pct_spot",
        "mean_abs_error_pct_spot", "p95_abs_error_pct_spot", "p99_abs_error_pct_spot",
    ]:
        _assert_series_close(hedging[column], expected_hedging[column], f"hedging diagnostic {column}", atol=1e-10, rtol=1e-6)

    reproduced = {
        "reference_capture_utc": captured,
        "raw_option_rows": int(len(raw)),
        "clean_option_rows": int(len(universe)),
        "fitted_expiries": int(len(fit_summary)),
        "median_svi_holdout_rmse_total_variance": float(fit_summary["holdout_rmse_total_variance"].median()),
        "median_quadratic_holdout_rmse_total_variance": float(fit_summary["quadratic_holdout_rmse_total_variance"].median()),
        "svi_holdout_wins_vs_quadratic": int(fit_summary["svi_beats_quadratic_holdout"].sum()),
        "calendar_violating_grid_points": int(calendar["violating_grid_points"].sum()) if len(calendar) else 0,
        "atm_iv_used_for_simulated_hedging": atm_iv,
        "status": "PASS",
    }
    (output / "reference_verification.json").write_text(json.dumps(reproduced, indent=2), encoding="utf-8")
    print(json.dumps(reproduced, indent=2))


if __name__ == "__main__":
    main()
