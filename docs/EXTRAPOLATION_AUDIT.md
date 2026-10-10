# Analytic density and unsupported-extrapolation audit

This extension challenges the **frozen September 2, 2026 raw-SVI parameters**.
It does not refit the six smiles, change the accepted holdout results, or claim
new market observations. Development includes AI assistance.

## Question and result

Do positive total variance, sub-2 asymptotic wing slopes and passing
observed-support call-shape checks justify extrapolating these fits?

**No.** Using the analytic density-sign factor in Gatheral and Jacquier,
[equation (2.1), Lemma 2.2](https://arxiv.org/abs/1204.0646):

| Domain | Smile density checks | Adjacent-expiry variance-order checks |
|---|---|---|
| Each smile's observed support / each pair's common observed support | 0/6 smiles with negative sampled density factor | 0/5 pairs with negative sampled variance increment |
| Explicit stress range `k ∈ [-3, 3]` | **2/6** smiles with negative density factor | **2/5** pairs with negative variance increment |

The stressed negative-density smiles expire September 18 and November 27,
2026. Their minimum sampled factors are approximately **-0.05837** and
**-0.11101**. Both minima in this stress scan occur at its left boundary;
these are **sampled minima on a finite interval**, not global minima.

The variance-order failures concern September 18 → September 25 and
November 27 → December 25. The common-moneyness calendar check is a
model-consistency diagnostic; it does not establish an executable trade
without the relevant carry, quotes and contract conditions.

All stress failures arise outside the corresponding observed/common-observed
supports. They are failures of fitted extrapolation, **not evidence of
executable arbitrage in the observed option market**.

## Method and checks

For raw SVI, derivatives of total variance are calculated analytically and
used in

`g(k) = (1 - k*w'(k)/(2*w(k)))² - w'(k)²/4 * (1/w(k) + 1/4) + w''(k)/2`.

The implementation scans 4,001 points on each observed domain and 12,001
points on the stress domain, with a negative tolerance of `1e-10`. The
source fit-table SHA-256 and actual execution environment are retained in
the result JSON. No stress endpoint or parameter is selected to improve
holdout performance.

Tests compare the analytic result with independent five-point numerical
differentiation of Black call prices with respect to strike, recover the
constant-volatility special case, and retain a real counterexample that
passes the structural constraints while producing negative density.

## Evaluation guard and limitations

`SupportedSVISlice(params, observed_k_min, observed_k_max).total_variance(k)`
rejects non-finite inputs and any request outside the declared observed
support. All six frozen slices reject the stress-domain request. This is an
explicit bounded-interpolation API. It is **not** a global no-arbitrage
calibrator and has not been deployed in a pricing service. Raw SVI functions
remain available as deliberately unguarded research primitives.

The alternating-strike benchmark also contains **3 boundary-extrapolation
test strikes out of 116**, one in each of three expiries. It is a held-out
strike-prediction benchmark, not a pure interpolation benchmark. These points
are inside the full observed data range but outside the corresponding
training-strike range. Existing numerical scores are preserved, with the
split distinction exposed in the result files.

Positive sampled density does not prove positivity between points or over
all real strikes. A globally arbitrage-free parameterization and multiple
dated market snapshots remain substantive future comparisons. This is a
replication and model-risk contribution; the analytic density criterion is
prior published work, not a newly invented theorem.

## Reproduce and inspect

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest tests -q
python run_density_audit.py
```

- [Protocol, source hash, environment and aggregate result](../reference/density_audit/summary.json)
- [Per-smile observed/stress results](../reference/density_audit/slice_diagnostics.csv)
- [Per-pair common-support/stress results](../reference/density_audit/calendar_diagnostics.csv)
- [Holdout interpolation/boundary-extrapolation audit](../reference/density_audit/split_diagnostics.csv)
- [Analytic implementation and support guard](../src/vol_surface/density.py)
- [Independent call-differentiation and adversarial tests](../tests/test_density.py)

The existing accepted-reference and cost-aware hedging workflows remain in
CI. The new audit executes on the frozen published parameters even if a new
numerical calibration finds a different, weakly identified parameter vector.
