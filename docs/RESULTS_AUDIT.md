# Adversarial results audit — FLAGSHIP-VOL-001

## Scope and evidence freeze

This audit interprets the live Deribit BTC-options snapshot captured at **2026-09-02T10:23:28Z** by CI run **33619168985** after the SVI implementation was structurally reparameterized and challenged against a simpler quadratic total-variance baseline.

The snapshot contained **978 raw option rows**. The frozen liquidity, DTE and moneyness filters retained **466 rows**, producing **6 calibrated expiries**. Raw source payloads are retained and hashed. This is a single timestamped cross-section; it is not historical option P&L or a claim about persistent surface dynamics.

## Calibration challenge

The primary cross-sectional validation metric is alternating-strike holdout RMSE in total variance. The same holdout is also evaluated with a simple quadratic-in-log-moneyness baseline fitted only on the training strikes.

Across the six fitted expiries:

- median SVI holdout RMSE: **0.00017263** total variance;
- median quadratic holdout RMSE: **0.00032092** total variance;
- SVI beats the quadratic baseline on **4 of 6** expiries;
- on the two nearest expiries, the quadratic baseline is slightly better.

This means the SVI architecture is useful in the richer slices but is **not uniformly superior to a much simpler cross-sectional curve**. That negative complexity result is retained. The project does not claim that SVI is empirically necessary for every expiry in this snapshot.

## Shape diagnostics

The reparameterized raw-SVI slices guarantee positive analytic minimum total variance and asymptotic total-variance wing slopes below 2. On the observed strike support, the Black-76 call-price diagnostics report:

- **0** negative-total-variance grid points;
- **0** call-monotonicity violations;
- **0** call-convexity violations.

The common log-moneyness calendar diagnostic over adjacent fitted expiries reports **0 violating grid points**. These are numerical diagnostics over the documented grids and observed support; they are **not** a proof of a globally arbitrage-free continuous surface.

## Parameter identifiability warning

Two of six full-sample fits place the raw-SVI center parameter `m` outside the observed log-moneyness range. One near-dated slice also has a very large `sigma / observed-k-span` (above 8 in the accepted fit). The corresponding curves still satisfy the structural and observed-support shape diagnostics, but individual raw-SVI parameter values are therefore treated as **weakly identified curve parameters rather than economically interpretable quantities**.

Numerically equivalent reruns may move raw-parameter-derived extrapolation quantities while leaving the held-out errors and observed-support curve evidence essentially unchanged. Validation therefore requires the structural raw-SVI constraints to remain satisfied and gates the stable recruiter-facing curve evidence directly rather than requiring digit-for-digit raw-parameter identity.

This is why the recruiter-facing evidence emphasizes held-out curve error, baseline comparison and observed-support shape diagnostics instead of reporting raw parameter values as findings.

## Delta-hedging model-risk experiment

The hedging experiment is deliberately separated from the Deribit calibration evidence. It simulates a 30-day ATM option under GBM and measures terminal replication error under different hedge frequencies and volatility assumptions. It is not historical Deribit option P&L.

Using the snapshot ATM IV of **35.83%** as the simulated true volatility:

| Scenario | Mean absolute replication error / spot | 95th pct absolute error / spot |
|---|---:|---:|
| Hourly, correct vol | 0.1000% | 0.2738% |
| 6-hour, correct vol | 0.2422% | 0.6720% |
| Daily, correct vol | 0.4763% | 1.2828% |
| Hourly, vol -10 points | 1.1505% | 2.0425% |
| Hourly, vol +10 points | 1.1465% | 1.8026% |

The controlled result behaves as expected: discrete hedging error grows materially as rebalancing becomes less frequent, while volatility misspecification dominates the residual error in the ±10-point scenarios. The simulation is evidence of pricing/hedging implementation and model-risk reasoning, not a claim of tradable edge.

## Accepted conclusion

FLAGSHIP-VOL-001 is accepted as **research evidence** for derivatives/volatility/strats positioning, subject to the following recruiter-facing boundary:

1. claim a timestamped, source-hashed Deribit BTC option-surface study;
2. claim structurally constrained SVI calibration with alternating-strike holdout and a quadratic baseline challenge;
3. claim observed-support call-shape and common-grid calendar diagnostics with zero detected violations in this snapshot;
4. disclose that SVI loses to the quadratic holdout baseline on 2/6 expiries and that 2/6 slices show weak raw-parameter identification;
5. describe the hedging section explicitly as a controlled GBM model-risk simulation;
6. do **not** claim realized option P&L, a globally arbitrage-free surface, persistent market mispricing, trading alpha, or economically meaningful raw-SVI parameters.

This negative-evidence boundary is part of the project, not a caveat to be removed for presentation.
