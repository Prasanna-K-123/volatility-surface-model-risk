# Reference evidence manifest

This directory pins the recruiter-facing **reference result** independently of transient GitHub Actions artifacts or future market changes.

## Source identity

- Accepted analytical workflow run: `33619168985`
- Analytical commit: `b7458916d46e00bd6f217cf9f06b74f440c0475e`
- Deribit snapshot timestamp: `2026-09-02T10:23:28Z`
- Full raw `get_book_summary_by_currency` payload SHA-256: `9848861a047d1b3e4140506fbc6eaefbc6747074564dd5baeee98de7e158a66e`
- Full raw `get_instruments` payload SHA-256: `78a285534f0354af87a854b2ac8ac42fe623d7d3a23507ba8104c0dd54c77a84`

The accepted private validation run retained the complete raw responses. For this standalone recruiter-facing repository, `accepted_snapshot_inputs.csv.gz` pins all **978 merged option rows** and the exact pre-filter fields consumed by `clean_surface_universe`; CI therefore reruns the documented filtering and derived-variable pipeline before calibration. No redundant post-filter binary snapshot is required for reproduction.

## Reference outputs

The committed reference tables pin the accepted downstream evidence:

- `svi_fit_summary.csv`
- `calendar_arbitrage_diagnostics.csv`
- `delta_hedging_model_risk.csv`
- `research_summary.json`
- `snapshot_metadata.json`

`python verify_reference.py` reruns filtering, calibration, holdout comparison, static/calendar diagnostics and the hedging experiment from `accepted_snapshot_inputs.csv.gz`. It verifies the recruiter-facing evidence at the level actually claimed: fitted expiry identities, holdout/full-fit errors, baseline wins, curve-shape diagnostics, calendar checks and hedging errors. Raw SVI parameter values are deliberately not used as exact reproduction gates because weakly identified slices can move materially in parameter space without changing the fitted curve evidence; the project explicitly does not assign those raw parameters economic meaning.

A separate `python run_vol_research.py` execution intentionally queries the **current** Deribit market and is a new experiment, not a reproduction of the dated reference snapshot.
