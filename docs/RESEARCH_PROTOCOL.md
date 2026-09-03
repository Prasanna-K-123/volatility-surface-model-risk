# FLAGSHIP-VOL-001 pre-results protocol

## Question
Can a parsimonious SVI representation fit a liquid cross-section of BTC option mark implied volatilities with defensible cross-sectional holdout error while preserving basic static-shape diagnostics, and what does a controlled simulation show about delta-hedging sensitivity to rebalance frequency and volatility misspecification?

## Frozen design before snapshot inspection
- Venue/source: public Deribit BTC option endpoints.
- Snapshot: one timestamped production-market snapshot captured by CI; raw JSON is retained with SHA-256 digests.
- Universe: 7-180 DTE, |ln(K/F)| <= 0.65, finite bid/ask, positive mark IV, nonnegative open interest.
- Surface variable: Deribit `mark_iv` converted from percentage points to decimal volatility; no reverse-engineering of venue premium conventions.
- Minimum: >=10 unique strikes per fitted expiry.
- Model: raw SVI total variance, separately by expiry.
- Validation: deterministic alternating-strike holdout; fit on one strike subset and score on the other.
- Full fit: only after the holdout metric is recorded.
- Static diagnostics: total variance positivity, Black-76 call monotonicity/convexity on the observed strike span.
- Calendar diagnostic: fitted total variance must not decrease with maturity on a common central log-moneyness grid.
- Hedging experiment: GBM simulation, 30-day ATM call, hourly/6h/daily rebalance and +/-10 volatility-point misspecification.

## Non-negotiable evidence boundaries
- A one-time option-chain snapshot is not a trading strategy or forecast study.
- `mark_iv` is a venue mark, not an independently reconstructed executable IV.
- Static diagnostics are tests, not a mathematical proof that the entire interpolated surface is arbitrage-free.
- The hedging study is simulation evidence only; it is not realized-market P&L.
- Weak fit, arbitrage-diagnostic failures, or unstable hedging results remain visible.
