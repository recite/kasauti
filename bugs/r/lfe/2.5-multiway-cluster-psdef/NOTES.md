# lfe 2.5: multiway clustered standard errors from a non-PSD covariance

> Multiway clustered standard errors now incorporate the negative Eigenvalue
> adjustment of Cameron, Gelbach, Miller. I.e. they are forced to zero. Can be
> switched off by `felm(...,psdef=FALSE)`.
>
> — lfe NEWS, version 2.5 (first released 2016-04-11 as 2.5-1968)

## Why this one

`felm` is called by **244 corpus scripts**, the largest exposure of any candidate
in the study, and `lfe` is precisely the package the first, hand-written package
list forgot. It surfaced only after the frame was rebuilt from CRAN Task Views
intersected with corpus usage.

## No archived install was needed

Every other record here pins an old version in a side library. This one does not,
because the changelog ends by naming the flag that restores the old behaviour:
`psdef=FALSE`. One current version produces both answers, so the comparison is
immune to the usual archaeology failure — a 2016 package that no longer compiles
against a 2026 toolchain. **Where a changelog says a fix is revertible by
argument, take it**: the verification gets cheaper and strictly more reliable.

## The mechanism

The Cameron–Gelbach–Miller estimator for two clustering dimensions is

    V = V_firm + V_year − V_firm∩year

a *difference* of covariance matrices. Nothing constrains the result to be
positive semi-definite. When it is not, at least one eigenvalue is negative, and
the standard errors read off the diagonal claim precision the data does not
contain. Since 2.5, `lfe` clamps negative eigenvalues to zero.

## What was measured

A deterministic panel — 60 rows, 3 firms, 4 years, sine/cosine regressors, no RNG
— run through `lfe` 3.1.1 twice, once with each setting of `psdef`:

| quantity | `psdef=FALSE` (pre-2.5) | `psdef=TRUE` (current) | |
|---|---|---|---|
| smallest eigenvalue of clustered vcov | −5.256398e-03 | −1.9e-18 | negative, then zero |
| `se(x1)` | 0.012410243463 | 0.071774488067 | **corrected value is 5.78×** |
| `t(x1)` | 83.03 | 14.36 | |
| `se(x2)` | 0.08004115856 | 0.08020933127 | 2.1e-03 |
| `coef(x1)`, `coef(x2)` | identical | identical | relative difference exactly 0 |

Three things are worth separating.

**The size.** A standard error understated by a factor of 5.78 is the largest
single-quantity gap anywhere in this suite.

**The direction.** The superseded computation is the one reporting the *tighter*
interval. Bugs that inflate a standard error get caught by the author; bugs that
shrink one get published.

**The concentration.** `x2`'s standard error moves by 0.2% while `x1`'s moves by
83%. The damage lies along whichever direction the negative eigenvalue occupied,
so an analyst glancing at the rest of the table sees nothing unusual. That
localisation is why it is silent, and it is also the reason the case pins
`coef@x1` and `coef@x2` to AGREE: the adjustment touches the covariance and never
the point estimates, and a moving coefficient would mean the case measures
something other than what it claims.

I expected `se@x2` to fall inside `numeric_tol` and wrote that into the case
before running it. It does not — 2.1e-03 against a tolerance of 1e-05. The case
now expects DIVERGE and says what the number is.

## Silent before, loud after

Current `lfe` prints `Negative eigenvalues set to zero in multiway clustered
variance matrix. See felm(...,psdef=FALSE)` when the adjustment bites. That
warning is a property of the *fixed* version. Before 2.5 there was no adjustment
and therefore nothing to announce: the user received a finite, plausible, and too
small standard error with no signal at all. Hence `silent: true` — the field
describes the state of affairs before the fix.

One caveat on that. With `psdef=FALSE` a sufficiently negative diagonal produces
`NaN` standard errors, which is loud. In a scan of 400 random panels with 3–8
clusters per dimension, negative eigenvalues were common and `NaN` was rare — the
usual outcome was finite and wrong.

## Narrowing the exposure, and three probes that were wrong first

`scripts_calling_function` is 244. Getting `scripts_meeting_probe` right took
four attempts, and the failures are instructive because each one *looked* fine:

| probe | matched | what was wrong |
|---|---|---|
| `[^;]` between pipes | 58 | `[^;]` admits newlines, so the leading segment ran across statements and borrowed pipes from a *later* `felm` call |
| `[^\|;\n]` | 14 | fixed that, but multi-line `felm` calls — **115 of 244 scripts have one** — stopped matching, turning an upper bound into an undercount |
| `(?!felm)[^\|;]` | 26 | multi-line works again and it cannot slide into a neighbouring call, but it landed on the *instrument* field of IV specifications: `\| (x2 ~ z1 + z2) \|` |
| `(?!felm)[^\|;)~]` on the last field | **22** | a cluster field never contains `~`, so excluding it forces the match onto the real fourth field |

The lesson is the one this project keeps relearning: a plausible narrowing is
worth nothing until its matches are read. Inspecting all 22 shows genuine
two-way cluster specifications (`| respondent_id + ...`, `| hh_id + ...`,
`| firm + edu + id`) — with one match inside a commented-out line, since the
probe is a regex over source text where the call extractor uses R's own parser.

## Papers: a clean null, and why

22 scripts resolve to **12 archives**, of which **zero were published before
2016-04-11**. Nine carry dates from 2019 to 2024; three are undated.

This is the mirror image of the power problem recorded for the `sandwich` bugs.
There the fixes were recent (2018, 2022) and most of the corpus predated them, so
a small narrowed exposure still had papers in the window. Here the fix is *old*
and the corpus is recent, so everything using `felm` with two-way clustering was
run against a version that already had the adjustment.

The finding stands on its own terms — the computation was wrong, the correction
is large, and it is silent — but in this corpus it corrupted nothing. Recording
the null matters as much as recording the effect: an exposure of 244 scripts
narrowing to 22 and then to 0 affected papers is exactly the attrition the
pipeline exists to make visible, and reporting only the 244 would be a
five-order-of-magnitude overstatement of consequence.
