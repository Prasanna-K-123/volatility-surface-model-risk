# Validation and evidence policy

The recruiter-facing reference result is the fixed Deribit BTC option snapshot captured at `2026-09-02T10:23:28Z` and documented under [`../reference/`](../reference/). The complete raw API responses were retained by the accepted private validation run and are identified by SHA-256 in the reference manifest.

The reference pack commits the exact **978-row pre-filter analytical input** needed by `clean_surface_universe`, so the accepted 466-row calibration universe is regenerated rather than assumed. CI then reruns calibration, baseline comparison, observed-support static-arbitrage diagnostics, common-grid calendar checks and the controlled hedging-model-risk experiment.

The verifier intentionally distinguishes curve evidence from raw parameter identity. Weakly identified SVI slices may move in parameter space under tiny numerical perturbations; because the project does not interpret raw SVI parameters economically, exact parameter equality is not a validation gate. Holdout/full-fit errors, baseline wins, fitted-expiry identity, curve-shape diagnostics, calendar results and hedging evidence are the recruiter-facing gates.

`python run_vol_research.py` remains a live-market refresh path. A live refresh is deliberately treated as a **new timestamped experiment** and cannot silently replace the accepted reference result or its recruiter-facing claims.

The accepted evidence remains bounded to calibration quality, baseline comparison, observed-support static-arbitrage diagnostics, common-grid calendar checks and a controlled GBM hedging-model-risk experiment. It does not establish trading alpha, realized option P&L, executable arbitrage, persistent mispricing or a globally arbitrage-free surface.
