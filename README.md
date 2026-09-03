# Derivatives Volatility Surface, Static Arbitrage & Hedging Model Risk

[![Validation](https://github.com/Prasanna-K-123/volatility-surface-model-risk/actions/workflows/validation.yml/badge.svg?branch=main)](https://github.com/Prasanna-K-123/volatility-surface-model-risk/actions/workflows/validation.yml)

A reproducible derivatives-research project built around a timestamped public Deribit BTC option-chain snapshot. It calibrates structurally constrained raw-SVI total-variance slices, evaluates them on an alternating-strike holdout against a simpler quadratic baseline, challenges fitted surfaces with observed-support call-shape and common-grid calendar diagnostics, and separates real-market calibration evidence from a controlled delta-hedging model-risk simulation.

## Recruiter snapshot

| Signal | Verified evidence |
|---|---|
| Market snapshot | **978** timestamped raw option rows → **466** frozen-filter rows → **6** fitted BTC expiries |
| Complexity challenge | median SVI holdout RMSE **0.00017263** vs quadratic **0.00032092** total variance; SVI wins only **4/6** expiries |
| Static/calendar diagnostics | **0** observed-support call-monotonicity violations, **0** call-convexity violations and **0** common-grid calendar violating points |
| Model-risk experiment | hourly correct-vol mean absolute replication error about **0.100% of spot** vs about **1.15%** under ±10 volatility-point misspecification |
| Negative evidence retained | nearest two expiries favor the simpler quadratic baseline; **2/6** full fits place raw-SVI `m` outside observed support, so raw parameters are not given economic meaning |

**Direct evidence:** [`reference manifest`](reference/MANIFEST.md) · [`SVI fit summary`](reference/svi_fit_summary.csv) · [`calendar diagnostics`](reference/calendar_arbitrage_diagnostics.csv) · [`hedging model risk`](reference/delta_hedging_model_risk.csv) · [`adversarial results audit`](docs/RESULTS_AUDIT.md)

## Validated reference snapshot

The accepted reference snapshot was captured at **2026-09-02T10:23:28Z** and its analytical evidence is pinned under [`reference/`](reference/):

- **978** raw option rows in the hashed source snapshot;
- **466** rows after the frozen 7–180 DTE, quote-quality and moneyness filters;
- **6** fitted expiries;
- median SVI alternating-strike holdout RMSE: **0.00017263** total variance;
- median quadratic-baseline holdout RMSE: **0.00032092** total variance;
- SVI beats the quadratic baseline on **4/6** expiries;
- **0** observed-support call-monotonicity violations;
- **0** observed-support call-convexity violations;
- **0** common-grid calendar violating points across adjacent fitted expiries.

The two nearest expiries are a useful negative result: the simple quadratic holdout baseline slightly outperforms SVI. Two of six full fits also place raw-SVI `m` outside the observed log-moneyness range, so individual raw parameters are not interpreted economically when the slice is weakly identified.

## Research architecture

- timestamped Deribit production-market option snapshot with full raw-response SHA-256 provenance;
- committed 978-row pre-filter reproduction input containing every field consumed by the cleaning pipeline;
- documented 7–180 DTE liquidity/moneyness filters rerun in CI;
- raw-SVI calibration structurally parameterized for positive analytic minimum total variance and sub-2 asymptotic wing slopes;
- alternating-strike holdout before full refit;
- quadratic total-variance holdout baseline to challenge model complexity;
- Black-76 call monotonicity/convexity diagnostics over observed strike support;
- cross-expiry total-variance calendar checks on a common log-moneyness grid;
- simulated 30-day ATM delta-hedging experiment under hourly/6-hour/daily rebalancing and ±10 volatility-point misspecification;
- automated tests plus deterministic reference reproduction in CI;
- a separate live-refresh path for new market snapshots without rewriting the accepted result.

## Hedging model-risk result

Using the reference snapshot ATM IV of **35.83%** as the simulated true volatility, mean absolute terminal replication error is approximately:

- **0.100% of spot** with hourly correct-vol hedging;
- **0.242%** with 6-hour hedging;
- **0.476%** with daily hedging;
- about **1.15%** with hourly hedging but ±10 volatility-point misspecification.

This section is a controlled GBM model-risk experiment, not historical option P&L.

## Reproduce the accepted analysis

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest tests -q
python verify_reference.py
```

`verify_reference.py` reconstructs the filtered surface from the committed pre-filter snapshot fields, then reruns calibration, holdout comparison, static/calendar diagnostics and the hedging experiment. Source identities and evidence policy are documented in [`reference/MANIFEST.md`](reference/MANIFEST.md).

## Run a new live snapshot

```bash
python run_vol_research.py
```

This command intentionally retrieves the current public Deribit option market. Its numerical results are a new timestamped experiment and are **not** substituted for the dated accepted reference result.

## Evidence boundary

No trading alpha, realized option P&L, executable spread, persistent market mispricing, economically meaningful raw-SVI parameter interpretation, or mathematically guaranteed globally arbitrage-free surface is claimed.

The complete adversarial interpretation is in [`docs/RESULTS_AUDIT.md`](docs/RESULTS_AUDIT.md). See also [`docs/RESEARCH_PROTOCOL.md`](docs/RESEARCH_PROTOCOL.md), [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md), and [`docs/VALIDATION.md`](docs/VALIDATION.md).
