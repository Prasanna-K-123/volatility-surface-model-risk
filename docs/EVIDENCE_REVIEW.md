# Evidence review: Derivatives & Hedging Model Risk

Independent portfolio research. Updated 2026-10-09. Development and documentation include AI assistance; the committed executable code, data provenance and test outputs establish the work products. No institutional endorsement or third-party authorship review is claimed.

## Research purpose

Numerical calibration, pricing diagnostics and hedging.

## Published evidence

466 filtered BTC option observations, 6 expiries; 27 common-path hedge/cost/volatility scenarios across 3,000 simulated paths.

## Interpretation boundary

One historical crypto-option snapshot and controlled GBM simulation; no global arbitrage-free or profitable-trading claim.

## Review standard

Check the source data and split before interpreting a score. Compare the strongest result with a simple baseline. Inspect failed diagnostics and uncertainty. Reproduce the calculations from the documented environment; distinguish measured findings from simulated or assumed scenarios. The tests cover specific documented invariants and do not establish complete production correctness.

## Next research extension

Collect multiple dated option snapshots, validate smile interpolation under temporal shifts and compare jump/stochastic-volatility simulations. Cost-aware GBM diagnostics are a completed extension, not a substitute for market execution data.
