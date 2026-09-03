from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vol_surface.data import clean_surface_universe, fetch_deribit_option_snapshot
from vol_surface.diagnostics import calendar_arbitrage_diagnostics, fit_summary_row, static_arbitrage_diagnostics
from vol_surface.hedging import hedging_experiment
from vol_surface.svi import evaluate_expiry, svi_total_variance


def main() -> None:
    root = Path(__file__).resolve().parent
    out = root / "results"
    raw = root / "data" / "raw"
    figs = root / "reports" / "figures"
    for p in [out, raw, figs]:
        p.mkdir(parents=True, exist_ok=True)

    snapshot, meta = fetch_deribit_option_snapshot("BTC", raw)
    universe = clean_surface_universe(snapshot, meta.captured_at_utc)
    universe.to_csv(out / "surface_universe.csv", index=False)

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

        grid = np.linspace(float(curve["k"].min()), float(curve["k"].max()), 201)
        iv = np.sqrt(np.maximum(svi_total_variance(grid, fit["params"]), 1e-12) / fit["T"])
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.scatter(curve["k"], curve["iv"], s=18, label="Deribit mark IV")
        ax.plot(grid, iv, label="SVI fit")
        ax.set_xlabel("log-moneyness ln(K/F)")
        ax.set_ylabel("implied volatility")
        ax.set_title(f"BTC options - {fit['expiry'][:10]}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(figs / f"surface_{fit['expiry'][:10]}.png", dpi=160)
        plt.close(fig)

    if len(fits) < 2:
        raise RuntimeError(f"Too few liquid expiries after filters: {len(fits)}")

    summary = pd.DataFrame(summary_rows).sort_values("T")
    calendar = calendar_arbitrage_diagnostics(fits)
    atm_idx = int(np.argmin(np.abs(universe["k"].to_numpy())))
    atm_iv = float(universe.iloc[atm_idx]["iv"])
    S0 = float(universe.iloc[atm_idx]["forward"])
    hedging = hedging_experiment(S0=S0, true_sigma=atm_iv)

    summary.to_csv(out / "svi_fit_summary.csv", index=False)
    calendar.to_csv(out / "calendar_arbitrage_diagnostics.csv", index=False)
    hedging.to_csv(out / "delta_hedging_model_risk.csv", index=False)
    (out / "snapshot_metadata.json").write_text(json.dumps(meta.__dict__, indent=2), encoding="utf-8")

    headline = {
        "snapshot": meta.__dict__,
        "clean_option_rows": int(len(universe)),
        "fitted_expiries": int(len(summary)),
        "median_svi_holdout_rmse_total_variance": float(summary["holdout_rmse_total_variance"].median()),
        "median_quadratic_holdout_rmse_total_variance": float(summary["quadratic_holdout_rmse_total_variance"].median()),
        "svi_holdout_wins_vs_quadratic": int(summary["svi_beats_quadratic_holdout"].sum()),
        "expiries_with_svi_m_outside_observed_range": int(summary["svi_m_outside_observed_range"].sum()),
        "total_static_convexity_violations": int(summary["call_convexity_violations"].sum()),
        "calendar_violating_grid_points": int(calendar["violating_grid_points"].sum()) if len(calendar) else 0,
        "atm_iv_used_for_simulated_hedging": atm_iv,
        "hedging_note": "GBM simulation diagnostic only; not realized option P&L.",
        "parameter_note": "Raw-SVI parameter values are not interpreted economically when the slice is weakly identified; curve fit, holdout error and shape diagnostics are primary evidence.",
    }
    (out / "research_summary.json").write_text(json.dumps(headline, indent=2), encoding="utf-8")
    print(json.dumps(headline, indent=2))


if __name__ == "__main__":
    main()
