# Registered multidate shape comparison — 2026-10-11

**Raw SVI fits the held-out marks more closely, while joint SSVI meets the registered idealized shape conditions at a material accuracy cost.** Neither result establishes current-market generalization, executable arbitrage or profitable trading. This is a retrospective comparison within the existing derivatives project, with every planned date, exclusion, fit and refusal accounted for.

## Source, registration and amendment

Nikolai Zaitsev (2019), *Data for: Empirical forward price distribution from Bitcoin option prices*, [Mendeley Data V2](https://data.mendeley.com/datasets/hfd4b8zfw6/2), DOI **10.17632/hfd4b8zfw6.2**, CC0 1.0. Archive SHA256: `69bb91c9640376a9065b97b2b472bc60c11819b8ffba6c1d66ac66d9291ab9e2`.

The [first design](MULTIDATE_SHAPE_PROTOCOL.md) was committed as `00c60fff7fcb57a5961116ddeae344832e2ff5a0` before archive collection. The archive's missing mark-IV fields and undocumented filename timezone required an explicit [pre-fit schema amendment](MULTIDATE_SCHEMA_AMENDMENT.md). Complete methods, tests and the SHA256 manifest were registered at `c84299c663c09ec4b8889ab947397600df156f1c` **before variance inversion or numerical comparison**. This is a two-phase registration with a documented amendment, not an unchanged first protocol or an untouched prospective holdout. No filter, objective, start, split, budget or stress grid was chosen after observing comparison results.

The fixed first filename time in [12:00,12:15) for each of 9–18 December 2018 produces **nine available dates**; **2018-12-09 remains missing**. Explicit summary GMT timestamps are around 11:00 UTC. Filename time is not confirmed noon UTC, and per-quote freshness/simultaneity is unverified. These adjacent convenience dates are dependent; no independent-date confidence interval, significance or forecast claim is made.

The archive contains BTC option mark prices rather than venue mark IV. Variance is reconstructed under a **zero USD discount-rate research convention**, using a futures-record index proxy to convert BTC premiums and each option's recorded underlying. This does not reproduce a validated historical venue IV algorithm. **285 of 796 eligible option rows reference an underlying identifier that differs from the option expiry**, including 274 rows used in modelled expiry groups and 11 rows in a group rejected for insufficient strikes. Those flags are retained. Historical discounting, economic forwards, mark construction and tails are not independently verified.

## Complete case accounting

- **1,868 raw option rows**, all retained in the hashed row/exclusion ledger; **796 eligible rows** under frozen filters.
- **28 candidate date/expiry groups**; one December 13 weekly group has only eight distinct strikes and is rejected by the registered minimum of ten. **27 eligible groups** enter all four methods.
- **195 held-out distinct strikes**: **182 interior**, **13 boundary**. Same-strike calls/puts remain together; training uses even positions and testing odd positions. The 182-strike common interior set is identical for every method.
- **216 fit records** (27 groups × four methods × training/full phases), **zero failed fits**. The convex call baseline explicitly refuses all **13 boundary predictions**, plus 27 stress-smile and 18 stress-calendar diagnostics outside support; refusals are not scored as zero error or counted as passes.
- **780 prediction rows** accounted for, **767 scored**, **268 metric rows** checked. Per-date held-out parameters/predictions are written before that date's full refit. All three starts for each joint SSVI optimization are retained. Original raw-SVI fitting is unchanged and reports whether a successful selected fit exists; it does not expose every individual original start's trace.

## Accuracy and shape tradeoff

Errors below are **arithmetic means of per-date/expiry RMSEs** across all 27 groups on the common interior set. They are not pooled strike-level RMSEs, population estimates or a claim of a statistically significant best model. Price errors are synthetic normalized Black call values under the research convention.

| Method | Variance RMSE | IV RMSE (percentage points) | Normalized call RMSE | Wider stress density failures | Wider stress calendar failures |
|---|---:|---:|---:|---:|---:|
| Raw SVI | 0.00243777 | 1.8418 | 0.00092878 | **23/27 smiles** | **15/18 pairs** |
| Quadratic variance | 0.00289739 | 2.2644 | 0.00121030 | **21/27 smiles** | **6/18 pairs** |
| Convex call price | 0.00762034 | 4.2388 | 0.00338969 | Refused outside support | Refused outside support |
| Joint constrained SSVI | 0.00687240 | 3.9786 | 0.00277668 | 0/27 on registered grid | 0/18 on registered grid |

Raw SVI beats the quadratic in **21/27** groups by variance RMSE; among all four methods, the minimum variance RMSE belongs to raw SVI in 20 groups, quadratic in five and SSVI in two. SSVI's common-interior IV error is higher than raw SVI on **every one of the nine date-level averages** below. Stronger shape structure is not presented as a free improvement in predictive fit.

| Date | Raw SVI IV RMSE | Quadratic IV RMSE | Convex call IV RMSE | Joint SSVI IV RMSE |
|---|---:|---:|---:|---:|
| 2018-12-10 | 2.7218 | 2.4341 | 4.7641 | 3.0154 |
| 2018-12-11 | 1.0792 | 0.9793 | 3.5158 | 1.6877 |
| 2018-12-12 | 1.3406 | 1.2584 | 3.4538 | 2.1559 |
| 2018-12-13 | 0.7531 | 0.8145 | 3.3241 | 1.7730 |
| 2018-12-14 | 1.6274 | 2.8662 | 3.9676 | 5.9696 |
| 2018-12-15 | 2.0721 | 3.4128 | 4.4450 | 6.7001 |
| 2018-12-16 | 3.0358 | 3.2147 | 5.2580 | 3.7031 |
| 2018-12-17 | 1.6394 | 2.6430 | 4.7412 | 6.6685 |
| 2018-12-18 | 2.3071 | 2.7561 | 4.6799 | 4.1341 |

The 13 boundary points are a separate extrapolation challenge. Their mean per-group IV RMSE is **5.6480 pp raw SVI**, **7.3507 pp quadratic**, **12.0895 pp SSVI**; convex prediction is refused. SSVI does not make extrapolation accurate merely by enforcing mathematical shape conditions. See the complete [metrics](../reference/multidate_shape/results/metrics.csv), [predictions](../reference/multidate_shape/results/predictions.csv) and [fit parameters](../reference/multidate_shape/results/parameters.json).

## What the shape evidence establishes

All 27 variance-model smiles pass the registered **4,001-point observed-support** density diagnostic; all 18 adjacent pairs pass the common-observed-support calendar diagnostic. The wider **12,001-point k ∈ [-3,3]** stress reveals the raw-SVI and quadratic failures above. The minimum stressed density factor is about **−1.46024 raw SVI**, **−0.14417 quadratic**, and **+0.26055 SSVI**. No nonpositive/nonfinite variance is found on these grids. Finite grids do not prove an unconstrained function safe between points or globally.

The convex call fit meets intrinsic/upper bounds, nonincreasing calls, slope bounds [-1,0] and nondecreasing slopes on its observed interval; the largest full-fit constraint error is **3.23e−13**. Its piecewise-linear density is a discrete measure, so smooth-density g is inapplicable. The 18 normalized-call calendar increments pass only on common support; this baseline is not jointly constrained across maturity. It refuses extension outside its fitted interval.

SSVI uses shared rho/eta and increasing theta with `phi(theta)=eta/sqrt(theta*(1+theta))`. The registered eta bound supplies sufficient butterfly inequalities; monotone theta and the derivative ratio supply the idealized calendar condition in [Gatheral & Jacquier](https://arxiv.org/abs/1204.0646). All **18 joint parameter sets** (nine dates × two phases) and **54 slice certificates** are checked. Its public API refuses maturity extrapolation and strike requests outside fitted/common interpolated support. Mathematical sufficient conditions do not validate this archive's forwards/discounting, economic contract mapping or unseen tails.

## Reproduction and verification

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest tests -q
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python run_multidate_shape.py --workers 4
python verify_multidate_shape.py
```

No live download is needed: the selected CC0 inputs preserve exact original nested JSON strings and member hashes. Selected input SHA256: `137cffb2923ac7e38047c3001fe58cee5576543e7b946450f25cbd02155234ac`. Method-manifest SHA256: `bccaf1fc4e535143bcbb88e7208557b9ccb8714ab7854349ac5958a468321185`. All 13 registered method/configuration identities are guarded before execution.

The complete registered CI run [38125191575](https://github.com/Prasanna-K-123/volatility-surface-model-risk/actions/runs/38125191575) executes all nine available dates and **45 unit tests**, then audits every raw row, 796 inversion residuals, 780 prediction identities, 767 successful predictions, 268 metrics and 54 certificates for each constrained method. It precedes frozen results, so its stored-reference comparison is explicitly skipped. This release freezes that run's 28 output files; later CI must execute the whole study and compare them. The separately executed local Python 3.12 study agrees with the CI Python 3.11 study at the **predeclared rtol 2e−4/atol 1e−8**, with exact identities, statuses and discrete counts. Optimizer evaluation counts and weakly identified coordinates are not platform-wide bit-identity promises.

An additional independent algebra check recomputes **162 smooth-density rows**, **27 convex constraint rows**, **126 scored calendar rows**, all 18 joint parameter sets and summary aggregation. These are automated internal checks, not external expert review or assessed candidate explainability.

## Prior evidence and limits remain

The original **978 raw / 466 filtered rows**, six September 2026 venue mark-IV expiries, **3 boundary points among 116 held-out strikes**, **2/6 wider density failures**, **2/5 wider calendar failures**, bounded raw-SVI API and **27 cost-aware scenarios on 3,000 common GBM paths** are unchanged. Their inputs, algorithms, tests and accepted results retain their exact identities. New reconstructed 2018 variance is a separate convention and is not pooled with that source.

This release completes the defined retrospective accuracy/shape comparison. A genuinely locked later-date test with validated historical contract/forward/discount data, robust live feed handling, economic execution costs, real trading use and independent review remain absent. No alpha, realized PnL, globally best model, current-market validation, practitioner endorsement or candidate mastery is claimed.
