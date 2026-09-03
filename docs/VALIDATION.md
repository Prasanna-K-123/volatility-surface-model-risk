# Validation and evidence policy

The recruiter-facing reference result is the fixed Deribit BTC option snapshot captured at `2026-09-02T10:23:28Z` and documented under [`../reference/`](../reference/). The complete raw API responses were retained by the accepted validation run and are identified by SHA-256 in the reference manifest.

The reference pack commits the exact **978-row pre-filter analytical input** needed by `clean_surface_universe`, so the accepted 466-row calibration universe is regenerated rather than assumed. CI then reruns calibration, baseline comparison, observed-support static-arbitrage diagnostics, common-grid calendar checks and the controlled hedging-model-risk experiment.

The verifier intentionally distinguishes stable curve evidence from raw parameter identity. Weakly identified SVI slices can move in parameter space across numerical environments without materially changing the fitted curve. Because the project does not interpret raw SVI parameters economically, digit-for-digit raw-parameter equality is not a validation gate. Holdout/full-fit errors, baseline wins, fitted-expiry identity, observed-support curve diagnostics, calendar results and hedging evidence are compared to the accepted reference, while positivity and wing-slope restrictions are enforced as structural constraints.

`python run_vol_research.py` remains a live-market refresh path. A live refresh is deliberately treated as a **new timestamped experiment** and cannot silently replace the accepted reference result or its recruiter-facing claims.

The accepted evidence remains bounded to calibration quality, baseline comparison, observed-support static-arbitrage diagnostics, common-grid calendar checks and a controlled GBM hedging-model-risk experiment. It does not establish trading alpha, realized option P&L, executable arbitrage, persistent mispricing or a globally arbitrage-free surface.
