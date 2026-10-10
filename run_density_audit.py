"""Challenge frozen SVI fits without recalibration or altering prior results."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy

from vol_surface.density import SupportedSVISlice, svi_density_factor
from vol_surface.data import clean_surface_universe
from vol_surface.svi import SVIParams, alternating_strike_holdout, svi_total_variance


def scan(k, p, tolerance=1e-10):
    g = svi_density_factor(k, p)
    i = int(np.argmin(g))
    return {"grid_points": int(len(k)), "minimum_g": float(g[i]),
            "k_at_minimum_g": float(k[i]), "negative_g_points": int(np.sum(g < -tolerance))}


def main():
    root = Path(__file__).resolve().parent
    source = root / "reference/svi_fit_summary.csv"
    output = root / "reference/density_audit"
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(source).sort_values("T").reset_index(drop=True)
    raw_source = root / "reference/accepted_snapshot_inputs.csv.gz"
    universe = clean_surface_universe(pd.read_csv(raw_source), "2026-09-02T10:23:28Z")
    splits = []
    for expiry, part in universe.groupby("expiry"):
        curve = part.groupby("strike", as_index=False).agg(k=("k", "mean")).sort_values("strike")
        if len(curve) < 10:
            continue
        train, test = alternating_strike_holdout(curve)
        outside = (test.k < train.k.min()) | (test.k > train.k.max())
        splits.append({"expiry": pd.Timestamp(expiry).isoformat(), "train_strikes": len(train),
                       "test_strikes": len(test), "test_strikes_outside_training_support": int(outside.sum()),
                       "train_k_min": float(train.k.min()), "train_k_max": float(train.k.max()),
                       "test_k_min": float(test.k.min()), "test_k_max": float(test.k.max())})
    split_frame = pd.DataFrame(splits)
    if split_frame.expiry.tolist() != frame.expiry.tolist():
        raise AssertionError("Holdout audit does not match the frozen expiry identities")
    split_frame.to_csv(output / "split_diagnostics.csv", index=False)
    extended = np.linspace(-3.0, 3.0, 12001)
    slices, params = [], []
    for row in frame.itertuples(index=False):
        p = SVIParams(**{key: float(getattr(row, "svi_" + key)) for key in ["a", "b", "rho", "m", "sigma"]})
        params.append(p)
        support = SupportedSVISlice(p, float(row.observed_k_min), float(row.observed_k_max))
        observed = np.linspace(support.k_min, support.k_max, 4001)
        support.total_variance(observed)
        try:
            support.total_variance(np.array([-3.0, 3.0]))
        except ValueError:
            rejected = True
        else:
            rejected = False
        record = {"expiry": row.expiry, "observed_k_min": support.k_min, "observed_k_max": support.k_max,
                  "stress_k_min": -3.0, "stress_k_max": 3.0, "out_of_support_request_rejected": rejected}
        record.update({"observed_" + key: value for key, value in scan(observed, p).items()})
        record.update({"stress_" + key: value for key, value in scan(extended, p).items()})
        slices.append(record)

    calendars = []
    for i in range(len(params) - 1):
        lo = max(float(frame.iloc[i].observed_k_min), float(frame.iloc[i+1].observed_k_min))
        hi = min(float(frame.iloc[i].observed_k_max), float(frame.iloc[i+1].observed_k_max))
        if lo >= hi:
            raise ValueError("Adjacent slices have no common observed support")
        common = np.linspace(lo, hi, 4001)
        row = {"near_expiry": str(frame.iloc[i].expiry), "far_expiry": str(frame.iloc[i+1].expiry),
               "common_observed_k_min": lo, "common_observed_k_max": hi}
        for label, grid in [("common_observed", common), ("stress", extended)]:
            delta = svi_total_variance(grid, params[i+1]) - svi_total_variance(grid, params[i])
            j = int(np.argmin(delta))
            row.update({label + "_grid_points": int(len(grid)), label + "_minimum_variance_increment": float(delta[j]),
                        label + "_k_at_minimum": float(grid[j]), label + "_negative_points": int(np.sum(delta < -1e-10))})
        calendars.append(row)

    slice_frame, calendar_frame = pd.DataFrame(slices), pd.DataFrame(calendars)
    slice_frame.to_csv(output / "slice_diagnostics.csv", index=False)
    calendar_frame.to_csv(output / "calendar_diagnostics.csv", index=False)
    summary = {
        "protocol_version": 1,
        "source_file": "reference/svi_fit_summary.csv",
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "snapshot_input_sha256": sha256(raw_source.read_bytes()).hexdigest(),
        "source_snapshot_utc": "2026-09-02T10:23:28Z",
        "calibration": "Frozen published parameters; no new fit or holdout tuning",
        "method_reference": "https://arxiv.org/abs/1204.0646, equation (2.1)",
        "grid_protocol": {"observed_points": 4001, "stress_min": -3.0, "stress_max": 3.0,
                          "stress_points": 12001, "negative_tolerance": 1e-10},
        "fitted_slices": len(slices),
        "observed_slices_with_negative_g": int((slice_frame.observed_negative_g_points > 0).sum()),
        "stress_slices_with_negative_g": int((slice_frame.stress_negative_g_points > 0).sum()),
        "adjacent_pairs": len(calendars),
        "common_observed_pairs_with_negative_variance_increment": int((calendar_frame.common_observed_negative_points > 0).sum()),
        "stress_pairs_with_negative_variance_increment": int((calendar_frame.stress_negative_points > 0).sum()),
        "support_guard_rejected_all_outside_requests": bool(slice_frame.out_of_support_request_rejected.all()),
        "holdout_test_strikes": int(split_frame.test_strikes.sum()),
        "holdout_test_strikes_outside_training_support": int(split_frame.test_strikes_outside_training_support.sum()),
        "holdout_slices_with_boundary_extrapolation": int((split_frame.test_strikes_outside_training_support > 0).sum()),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__},
        "interpretation": "Outside-support failures refute global safety of these frozen raw-SVI fits. They are not observed executable market arbitrage. Finite-grid passes are not global proofs. Cross-expiry variance ordering is a model diagnostic under a common-moneyness convention, not a carry-independent trading claim.",
        "deployment_decision": "Use SupportedSVISlice for bounded interpolation; reject unsupported extrapolation. Raw functions remain diagnostic research primitives; this guard has not been wired into a production pricing service.",
    }
    if (summary["fitted_slices"] != 6 or summary["stress_slices_with_negative_g"] != 2
            or summary["stress_pairs_with_negative_variance_increment"] != 2
            or summary["observed_slices_with_negative_g"] != 0
            or summary["common_observed_pairs_with_negative_variance_increment"] != 0
            or summary["holdout_test_strikes"] != 116
            or summary["holdout_test_strikes_outside_training_support"] != 3
            or not summary["support_guard_rejected_all_outside_requests"]):
        raise AssertionError("Frozen diagnostic findings changed; investigate instead of overwriting the claim")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
