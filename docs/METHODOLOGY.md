# Methodology

The project separates three questions that are often blurred together in portfolio work: cross-sectional calibration, static-shape sanity, and hedging-model risk.

For each qualifying expiry, observed total variance is `w = IV^2 T` with log-moneyness `k = ln(K/F)`. A raw SVI slice is fitted:

`w(k) = a + b [rho (k-m) + sqrt((k-m)^2 + sigma^2)]`.

The fit uses constrained nonlinear least squares with positivity and wing-slope penalties. The penalty is deliberately described as discipline rather than a proof of global no-arbitrage.

To avoid reporting only in-sample calibration, sorted unique strikes are split deterministically into alternating fit/test sets. SVI is fitted on the first set and total-variance RMSE is measured on the held-out strikes. The final reported curve may then be refit on all strikes for diagnostics and visualization.

Static shape is evaluated through Black-76 normalized call values on a dense grid across the observed strike span. Numerical first and second strike derivatives are inspected for monotonicity and convexity. Adjacent expiries are also compared on a central common log-moneyness grid for calendar total-variance inversions.

The hedging component is intentionally separate from the real snapshot. It simulates GBM with volatility anchored to the observed near-ATM mark IV, then compares discrete delta-replication errors under different hedge frequencies and +/-10 volatility-point model misspecification. This isolates discretization and parameter risk without presenting a synthetic path as realized trading performance.
