# Pre-fit schema amendment — 2026-10-11

The first design registration is commit `00c60fff7fcb57a5961116ddeae344832e2ff5a0`.
Metadata/collection commits are `130fb840005a03974af116531416d5ca570cdbf7`
and request-header/hash correction `968cf38bce5fb23ef4ff4076ca2265df0ffb9a9d`.
No new numerical fit or comparison was executed before this amendment.

## Actual source mismatch and retained selection

The verified 17,375,878-byte RAR has SHA256
`69bb91c9640376a9065b97b2b472bc60c11819b8ffba6c1d66ac66d9291ab9e2`.
It has 2563 `.txt` members containing JSON. Each payload contains `date`,
JSON-string encoded `options` and `futures`, and an unused `libor` array.
Option summaries have `markPrice` in BTC, `uPx`, `uIx`, `iR`, `openInterest`,
`bidPrice`, `askPrice`, `created` and instrument identifiers. **There is no
mark-IV field.** The originally specified direct mark-IV ingestion cannot run.

The same first filename time in [12:00,12:15) is retained for every registered
day. 2018-12-09 has no such member and remains missing. Nine selected members
remain; December 18's first is 12:05:04. Filename timezone is undocumented.
Their explicit `created` GMT values are around **11:00 UTC**, one hour behind
filename time. Do not label this confirmed noon UTC, infer a local timezone or
select a replacement hour. Use the explicit GMT summary timestamp for year
fractions, preserving both time representations. `created` is summary metadata;
per-instrument quote freshness and a simultaneous market snapshot are unverified.

## Explicit research price convention

To enable the same four-method comparison, reconstruct total variance from
option **mark prices**, not supplied venue IV. Use a fixed zero USD discount-rate
Black-forward convention. The index input S is the median positive `estDelPrice`
in that snapshot's futures records; record its cross-record dispersion. This is
an index proxy, not an independently archived spot feed. The underlying input U
is the option's recorded `uPx`; preserve `uIx` and flag whether its identifier
matches the option expiry. Some references use a different expiry or index.
No silent interpolation, substitution of futures or fitted carry is performed.

Convert BTC premium P to USD as P*S, then normalize by U. For a call,
`c = P*S/U`; for a put, the convention's call equivalent is
`c = P*S/U + 1 - K/U`. Solve `c = N(d1) - (K/U)*N(d2)` for w using the frozen
positive variance bracket [1e-12,100] and brentq xtol 1e-14. Inversion outside
strict intrinsic/upper call bounds, absent/nonpositive premium, invalid inputs
or an unbracketed root is a recorded exclusion. No clipping or repaired price.
Derived IV is sqrt(w/T), subject to the same [.05,3] limits. The original quote,
index/underlying, conversion rate assumption, inversion residual and exclusion
reason remain auditable. Retain nonzero `iR` as a mismatch flag; don't pretend the
zero-rate convention reproduces the venue's historical IV algorithm.

Deribit documents inverse-option BTC premiums and conversion using the index:
https://support.deribit.com/hc/en-us/articles/31424939096093-Inverse-Options
https://support.deribit.com/hc/en-us/articles/25944775983133-USD-Order-Options
The v1 field meanings are in the registered historical API reference. Current
contract/pricing descriptions do not independently establish the 2018 algorithm.

This convention is explicit but conditional. Unknown historical discounting,
nonmatching underlying maturities, index proxies and mark construction prevent
claims of accurately reconstructed venue IV, executable no-arbitrage or validated
economic forwards. The SSVI theorem applies to its mathematical parameterization
under common-moneyness assumptions, not a guarantee for these observed contracts.

All selection windows, min-strike/DTE/moneyness limits, four methods, splits,
optimizer starts/budgets, scoring and diagnostic grids remain unchanged.
Publish complete implementation/method hashes before running inversion or fits.
Prior 978/466-row venue mark-IV data and all prior results remain byte-identical.

## Collection history

Metadata run 38124216150 completed its script, but its only HTTP200 body was an
API error; it is not successful source resolution. The metadata check was fixed.
Collection run 38124352423 resolved authoritative metadata but its independent
default-header metadata request received HTTP403 before archive download.
Run 38124504703 with the same identifying research header and strict source
size/hash checks collected the archive. No credential, fee or access bypass.
These source-stage repairs precede all numerical outcomes.
