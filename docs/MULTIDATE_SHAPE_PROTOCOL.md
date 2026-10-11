# Multidate shape comparison — registration before collection

Status: design locked before downloading the new archive or running any new fit.
The existing September 2026 snapshot, all prior results, bounded raw-SVI API and
27 hedge scenarios remain unchanged. This is an extension within project 5.

## Question and evidence status

Compare held-out-strike accuracy and shape risk of four fixed methods across
dated BTC option snapshots. No method is assumed to win. The new source is an
author's retrospective convenience archive, not a randomly sampled market,
untouched prospective holdout, trading study or current-market validation.

Source: Nikolai Zaitsev (2019), *Data for: Empirical forward price distribution
from Bitcoin option prices*, Mendeley Data V2, DOI 10.17632/hfd4b8zfw6.2,
https://data.mendeley.com/datasets/hfd4b8zfw6/2. The record identifies JSON
Deribit option/futures snapshots for 9–18 December 2018 and CC0 1.0.
Archive: `dump_deribit_09-18-dec-2018.rar`, approximately 16.6 MB.
Record exact download identity, archive SHA256 and member hashes after receipt.
Do not download Tardis data: current public-data/model reuse terms are unsuitable
for this portfolio. No Tardis observations or fitted models enter this study.

## Fixed source selection and schema check

For each of the ten calendar days 2018-12-09 through 2018-12-18, select the first
snapshot timestamp at or after 12:00:00 UTC and before 12:15:00 UTC. Ties use
lexicographic archive-member order. Missing targets remain missing; no replacement
hour, day, asset or archive. Source naming/JSON wrapper may be inspected solely
to implement the registered extraction. Document any schema amendment before
fitting. Snapshot timestamps are collector observations, not simultaneous quotes.
If timezone cannot be established, report that limitation and do not call the
targets confirmed noon UTC.

Consume venue `markIv`/`mark_iv` as volatility percentage points divided by 100,
and venue `uPx`/`underlying_price` as its IV underlying convention. Do not infer
missing volatility from option premiums, use last-trade IV or silently replace
an underlying with spot. Parse expiry/strike/call-put from metadata or the dated
instrument identifier; expiry time 08:00 UTC follows the venue metadata/API.
Quotes/open interest map from documented summary/order-book fields. Missing
required schema halts that target, with its reason retained. The v1 venue field
reference is https://deribitexchange.gitbooks.io/deribit-api/content/rpc-endpoints.html.

Filters: 7–180 days to expiry, |log(K/U)| <= .65, positive finite strike/underlying,
decimal IV in [.05, 3], finite bid and ask, and nonnegative available open
interest. If open interest is absent from this historical format, explicitly
register its exclusion before any fit; do not fabricate a value. Keep a row
ledger of all exclusions, negative/crossed quotes and quote timestamp ranges.
No volume, positive spread or positive bid requirement is retroactively added.
Call and put marks at a strike average total variance with equal weight.
The new curve uses one median IV underlying per expiry and recomputes k at each
strike; retain relative underlying dispersion and the original row convention.
This convention is a modelling input, not independently verified USD forwards.
At least 10 distinct strikes and 5 training strikes per expiry are required.

## Frozen split, objectives and methods

Sort distinct strikes; even-position strikes (0,2,4,...) are training and odd
positions held out, as in the historical experiment. Same-strike calls/puts stay
together. Report interior tests separately from any test outside training
support. All four methods are compared on the common interior domain. Boundary
tests are a separate extrapolation challenge for the three variance methods;
the convex price fit refuses them. Record every eligibility/solver failure.
No day or expiry is omitted because a method fits badly.

1. **Raw SVI:** existing `fit_svi`, unchanged four starts and structural bounds.
2. **Quadratic variance:** ordinary degree-2 fit on training k and variance;
   invalid/nonpositive prediction remains a recorded failure, not clipped.
3. **Convex normalized call fit:** least squares to synthetic normalized Black
   call values implied by training marks, on x=K/U. Linear constraints enforce
   intrinsic <= call <= 1, slopes in [-1,0], and nondecreasing adjacent slopes.
   Piecewise-linear interpolation only inside the training interval. Invert
   valid calls to total variance; no smooth-density or global-tail claim.
   SLSQP maxiter 4000, ftol 1e-12; require constraint error <=1e-8 and record
   optimization status and price adjustment. Objective differs from variance
   least squares, so compare their prediction errors rather than objectives.
4. **Joint constrained SSVI:** fit all eligible expiries at each date with one
   rho and eta, increasing positive ATM total variances. Fixed modified power
   function phi(theta)=eta/sqrt(theta*(1+theta)); enforce |rho|<.999 and
   eta*(1+|rho|)<1.999. Three fixed starts: rho=-.4/0/.4, eta fraction .25/.5/.75;
   increasing theta initialization from cumulative maximum training ATM marks.
   Bounded transformed least squares, max_nfev 20000, tolerances 1e-11.
   Each expiry's mean squared variance residual divided by its median training
   variance squared gets equal weight, independent of its number of strikes.
   Lowest successful training objective wins. No held-out data chooses starts,
   parameters, objective, filters or comparison scope. Record all starts.

SSVI follows Gatheral & Jacquier, https://arxiv.org/abs/1204.0646, Eq.(4.1),
Corollary 4.1 and modified phi in Eq.(4.5). For this fixed phi the derivative
ratio (theta*phi)'/phi=1/[2(1+theta)] lies in (0,.5), and the eta bound supplies
the sufficient butterfly inequalities for all theta>0. Monotone theta supplies
the calendar condition in the idealized common-moneyness model. Interpolate
theta linearly only between fitted maturities; refuse maturity extrapolation.
The theorem concerns the mathematical parameterization under its assumptions,
not executable venue arbitrage, calibration accuracy or validated market tails.

## Fixed reporting and acceptance criteria

Keep strike-level predictions/residuals, split/eligibility ledgers, all full and
training fit parameters and solver failures. Metrics: total-variance RMSE and
MAE, IV RMSE in percentage points, synthetic normalized-call RMSE. Aggregate
within expiry, then give each date/expiry equal weight and report every date.
No p-value or independent-date confidence interval: ten adjacent days are
dependent, selected convenience data. No post-result significance claim.

After holdout recording, refit on all strikes for shape diagnostics. Raw-SVI
and SSVI use analytic density g on 4001 observed-support points and 12001
stress points k in [-3,3], tolerance 1e-10. Quadratic uses analytic derivatives
where variance is positive, recording nonpositive variance separately. Adjacent
calendar checks use 4001 common-support and 12001 stress k points. Price baseline
reports exact slopes and refuses beyond its observed support; its unsmoothed
density is a discrete measure and is not put through a smooth g test. These
finite grids do not certify an unconstrained model between points or globally.
Preserve the already known 2/6 far-support density failures and 3/116 original
boundary tests separately, with no rewriting of their source/results.

Acceptance is complete case accounting, no training/test leakage, verified
formula/constraint implementation, bounded APIs and reproducible honest outcomes.
A worse SSVI error, failed solver or model refusal does not invalidate the study
and must remain visible. No universal model-best or SOTA declaration.

## Two registration phases

This first public commit fixes source, selection, comparisons and numerical
choices before collection. After schema-only inspection, publish the complete
extractor, fitting/diagnostic code, meaningful tests and method SHA256 manifest
before executing the numerical comparison. Any necessary schema correction is
explicit, dated and separate; do not call it an untouched first registration.
Retain the archive locally for extraction; publish only CC0 selected inputs,
provenance, methods and outputs needed to reproduce the study. Old repository
blobs other than an appended README release note remain byte-identical.
