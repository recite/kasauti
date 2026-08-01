# sandwich 2.5-0: severe, and almost entirely harmless

The changelog entry that started this, from sandwich 2.5-0 (2018-08-17):

> Fix of a bug in `vcovHC.mlm()` (reported by James Pustejovsky). The
> off-diagonal values of the `vcovHC()` were computed without preserving the
> sign of the underlying residuals. This issue did not affect the diagonal
> because the underlying cross product amounts to squaring.

Run under both versions on identical data, the entry is exactly right:

| quantity | 2.4-0 (buggy) | 3.1-2 (fixed) | |
|---|---|---|---|
| `y1:(Int), y1:(Int)` | 0.03951860763 | 0.03951860763 | identical |
| `y1:(Int), y1:x` | -0.05741830386 | -0.05741830386 | identical |
| `y1:x, y1:x` | 0.09865280883 | 0.09865280883 | identical |
| `y2:(Int), y2:(Int)` | 0.04561492518 | 0.04561492518 | identical |
| `y2:(Int), y2:x` | -0.08266779969 | -0.08266779969 | identical |
| `y2:x, y2:x` | 0.2017457929 | 0.2017457929 | identical |
| **`y1:(Int), y2:(Int)`** | **+0.03366561558** | **-0.01938127953** | sign flip |
| **`y1:x, y2:x`** | **+0.109997852** | **+0.003342536347** | **33x** |
| **`y1:(Int), y2:x`** | **-0.05430599649** | **+0.01866536927** | sign flip |
| **`y1:x, y2:(Int)`** | **-0.05430599649** | **+0.01866536927** | sign flip |

Not "close" on the within-equation block — bit-identical, relative difference
exactly zero. The cross-equation block is wrong in sign, and in one case wrong
by a factor of 33.

## What that means for a reader of the changelog

"The off-diagonal values of `vcovHC()` were computed without preserving the
sign" reads like every standard error from the function was suspect for however
long the bug was live. It wasn't. **Ordinary per-coefficient standard errors
come off the diagonal and were never affected.** What was wrong is the
covariance *between coefficients of different equations* — which you only touch
if you run a joint test across equations: a Wald test that the `x` effect is
equal across responses, an SUR-style contrast, a cross-equation restriction.

So severity and blast radius point in opposite directions, and both are needed:

- **Severity: high.** Where it applied, the number was not slightly off. It had
  the wrong sign, silently, and a joint Wald test built on it could point the
  wrong way.
- **Exposure: about one script.** The bug is in the `.mlm` method — `lm()` with a
  matrix response, `lm(cbind(y1, y2) ~ x)`. Across 9,343 parsed R scripts in the
  replication corpus, 79 call `vcovHC` and 9 fit a multivariate `lm`; **1 does
  both**. Reporting this as "79 scripts exposed" would overstate it by roughly
  two orders of magnitude.

That gap is the reason the linkage pipeline carries a `conditions` field per bug
and why exposure has to be narrowed by it, not just by function name. Counting
every caller of an affected *function* is the wrong denominator whenever a bug
fires only under a specific method or argument.

## Why this case lives in `cases/`

It is the archaeology track's verification stage, and it is an ordinary
comparison case — two backends, one script, the same result schema. The only
difference from `hac_newey_west` is that the backends are two versions of one
package rather than two languages:

```yaml
backends:
  - name: buggy
    cmd: ["Rscript", "--vanilla", "run_r.R", "/tmp/rlibs/sandwich_2.4-0"]
  - name: fixed
    cmd: ["Rscript", "--vanilla", "run_r.R"]
```

That is the claim behind running both halves of the project on one engine, and
this case is the evidence for it.

## Reproducing

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/sandwich/sandwich_2.4-0.tar.gz",
  repos = NULL, type = "source", lib = "/tmp/rlibs/sandwich_2.4-0")'
kasauti run sandwich_mlm_sign
```

The `buggy` backend is marked `optional`, so the suite still runs without the
side library installed — it reports the backend as skipped rather than failing.

## It was wrong from the day it shipped

Bisected against archived CRAN versions: `vcovHC` had no `mlm` method at all in
2.2-3 (2009-11-30), and the first version that had one, 2.2-4 (2009-12-07),
already computed the off-diagonals with the wrong sign. The fix landed in 2.5-0
on 2018-08-17.

**8.7 years and 31 releases.** And nobody broke it -- the method was wrong when
it was written, which is a different claim from a regression and worth keeping
separate. A regression has a culprit commit and a window; this has neither, and
its exposure window is simply the whole life of the feature.

Five probes settled it, which is the argument for bisecting rather than scanning:
an R source install of a 2009 package takes a minute or two, and 31 of them would
have taken an afternoon.

The first attempt took nineteen probes and gave up unbracketed, because it treated
"the backend errored" as "cannot tell". Three of those errors said `no applicable
method for 'vcovHC' applied to an object of class "c('mlm', 'lm')"` -- which is
not a failure to evaluate, it is the answer. A bug in a method nobody has written
is not a bug. Everything older than 2008 fails differently and genuinely cannot be
judged: `ERROR: a 'NAMESPACE' file is required`, because R made them mandatory,
which is a hard floor on how far back R archaeology reaches at all.
