# plm 1.5-13: the reading said silent, the run said it errors

> fixed bug in `vcovHC(..., method="white")` from degenerating `diag()` if any
> group has only 1 element.
> — plm 1.5-13, undated

This entry was picked off the top of the classification shortlist: 76 corpus
scripts call `vcovHC`, and a panel with a singleton group is about as ordinary a
condition as this record contains — any unit that enters and leaves within a
period, or is cut to one usable row by missingness, produces one. It was
classified `RESULT_CHANGING` with `silent: true`.

**Running it refuted that.**

| | plm 1.5-12 | plm 2.6.7 |
|---|---|---|
| balanced, `arellano` | 0.06173696489 | 0.06173696489 |
| balanced, `white1` | 0.1161825457 | 0.1161825457 |
| **balanced, `white2`** | **0.1161825457** | **0.1271608291** |
| singleton, `arellano` | 0.06173696489 | 0.06173696489 |
| **singleton, `white1`** | **raises** | 0.1161825457 |
| **singleton, `white2`** | **raises** | 0.1271608291 |

With a singleton group, plm 1.5-12 raises `non-conformable arguments` and
returns nothing at all. R's `diag()` on a length-one numeric returns an identity
matrix of *that size* rather than a 1×1 — the classic footgun — and the
dimension mismatch propagates to an error rather than to a plausible-looking
wrong covariance.

So the record is `ERROR_TO_WORKING`, `silent: false`, severity `LOW`. A loud
failure never reaches a published table. The classification has been corrected
in `data/classify/reviewed.json` with a note saying verification is what
corrected it.

## Why this is the most useful of the four verified bugs

It is the first case where **verification overturned the reading rather than
confirming it**, and it does so in the direction a hopeful analyst would err.
"Fixed bug in vcovHC ... degenerating diag()" reads like a silently wrong
covariance matrix. Reading the sentence gets you that. Only running it gets you
the truth.

That has a consequence for the headline number. `docs/classification.md` reports
90 entries that could have moved a number in a published table, of which 86 are
silent result-changing bugs. That figure comes from reading, and reading has now
been shown to be wrong in this direction at least once. Four bugs have been
verified; **one had its classification overturned**. One in four is far too small
a sample to correct the 90 by, but it is large enough to say the 90 is an upper
bound rather than an estimate, and that the way to tighten it is to run more of
them.

## Two things that are not this bug

**`white2` on a balanced panel also moves** — 0.1161825457 to 0.1271608291, with
no singleton anywhere. In 1.5-12, `white2` returned exactly what `white1`
returned; by 2.6.7 it is a distinct estimator. Ten years and the whole 1.6 and
2.x series separate the two backends, so this is recorded as an observation
about the version span rather than attributed to the 1.5-13 entry. It is the
cost of the only pinning available: plm has no release under 1.5-13 in crandb at
all, so the nearest pre-fix version is 1.5-12 and the nearest post-fix is
current.

**The paper count is undeterminable, not zero.** plm's changelog does not date
1.5-13, so no archive can be placed relative to the fix. The pipeline used to
record that as `papers_in_window: 0`, which reads as "no papers affected" when
the truth is "no way to tell" — the same conflation the left-censored bucket
exists to avoid. It now records `None` and says so. Eleven scripts across eight
archives match the conditions probe; whether any predate the fix is unknown.

## An earlier version of this case was wrong

The first data generator made the response an exact linear function of the
regressors. Every method returned a standard error of `0.000000000000` under
both versions, the case passed, and it showed nothing. The response now carries
a component at a frequency the regressors do not, so the residuals are real. A
case that agrees because there is nothing to disagree about is worse than no
case.

## Reproducing

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/plm/plm_1.5-12.tar.gz",
  repos = NULL, type = "source", lib = "/tmp/rlibs/plm_1.5-12")'
concord run plm_vcovhc_singleton
concord bug probe r/plm/1.5-13-vcovhc-white-singleton
```
