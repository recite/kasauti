# Sampling frame

Which statistical procedures are worth testing, and which packages are
worth mining for result-changing bugs, derived from what published
replication archives actually call rather than from what seemed likely to
break.

## Corpus and coverage

| language | scripts | parsed | failed | parse rate | call sites |
|---|---|---|---|---|---|
| Python | 6526 | 6233 | 293 | 95.5% | 155460 |
| R | 9857 | 9343 | 514 | 94.8% | 242382 |

Parsing uses each language's own parser -- R's `getParseData`, Python's
`ast` -- not regular expressions, so a name in a string or a comment is
not counted as a call. Scripts that fail to parse are counted, not
dropped; that rate is a property of the archives.

## Which packages

The frame covers **132** packages, selected by
intersecting two sources, neither of them the author's memory: the
packages CRAN's expert-maintained Task Views list for a field, and the
packages replication archives in the corpus actually load. A package
qualifies by being both recognized by the field and used in the
literature.

The earlier version of this frame named its packages by hand. Measuring
the corpus afterwards showed what that costs: `lfe`, loaded by 222
archives, had simply been forgotten -- and a package left off the list is
indistinguishable from a package with nothing wrong.

Judgment survives in two exclusion rules, both stated at the level of a
category rather than a package, and both falsifiable in a way an
inclusion list is not. `INFERENTIAL_VIEWS` picks which of CRAN's 49 views
describe inference rather than infrastructure or a distant laboratory
domain. `NON_INFERENTIAL` drops packages whose whole job is plotting,
formatting, or data manipulation -- unavoidable, because `ggplot2` is
genuinely part of the Spatial and NetworkAnalysis toolkits, so no choice
of views excludes it.

## How a call is attributed to a package

**R.** A name is attributed to every package in the frame that exports
it, read from the `NAMESPACE` inside the CRAN source tarball rather than
from a hand-written table. Names the tidyverse routinely masks -- `filter`,
`select`, `lag`, `slice` -- count only when written `pkg::name`, since a
bare `filter()` in a script that loads dplyr is dplyr's. That rule
discarded 13148 script-function pairs, which is the
conservative direction: genuine bare `stats::filter` uses are lost, but
nothing is overcounted.

**Python.** Callees are resolved through each file's own import
statements, so `sm.OLS` counts as statsmodels only because of `import
statsmodels.api as sm` above it. A callee that does not trace to an
import -- a method on a local object -- is left unattributed. Without
this, common method names like `index` and `time` are indistinguishable
from package functions.

Plotting, printing, extraction, and family constructors are excluded: a
bug in `ggplot2`, the corpus's most-used package overall, does not change
a reported coefficient.

Exports come from the `NAMESPACE` inside each package's CRAN source
tarball, not from an installed copy, so coverage is not limited to what
one machine can build. Base packages, which have no tarball, are read
from the interpreter.

No export list resolved, so nothing can be attributed to them: `mapdata`.

## Top procedures, R (n = 9343 parsed scripts)

| # | function | package | scripts | share |
|---|---|---|---|---|
| 1 | `length` | Matrix | 3268 | 35.0% |
| 2 | `names` | raster | 1954 | 20.9% |
| 3 | `rep` | Matrix;memisc | 1887 | 20.2% |
| 4 | `is.na` | Matrix | 1820 | 19.5% |
| 5 | `nrow` | raster | 1739 | 18.6% |
| 6 | `as.numeric` | Matrix;memisc | 1486 | 15.9% |
| 7 | `mean` | Matrix;raster | 1412 | 15.1% |
| 8 | `cbind` | mice | 1353 | 14.5% |
| 9 | `unique` | memisc;raster | 1245 | 13.3% |
| 10 | `rbind` | mice | 1233 | 13.2% |
| 11 | `which` | Matrix | 1067 | 11.4% |
| 12 | `ggplot` | rms | 985 | 10.5% |
| 13 | `as.character` | memisc;raster | 948 | 10.1% |
| 14 | `log` | raster | 855 | 9.2% |
| 15 | `ncol` | raster | 820 | 8.8% |
| 16 | `as.data.frame` | raster | 739 | 7.9% |
| 17 | `dim` | Matrix;memisc | 724 | 7.7% |
| 18 | `rnorm` | stats | 690 | 7.4% |
| 19 | `as.integer` | Matrix;memisc | 668 | 7.1% |
| 20 | `lm` | stats | 643 | 6.9% |
| 21 | `sample` | memisc | 638 | 6.8% |
| 22 | `as.matrix` | Matrix;raster | 620 | 6.6% |
| 23 | `merge` | memisc;raster;sp | 589 | 6.3% |
| 24 | `subset` | raster | 546 | 5.8% |
| 25 | `as.vector` | Matrix;memisc;raster | 518 | 5.5% |
| 26 | `diag` | Matrix | 466 | 5.0% |
| 27 | `head` | Matrix;memisc;raster | 446 | 4.8% |
| 28 | `quantile` | raster;stats | 420 | 4.5% |
| 29 | `as.Date` | zoo | 416 | 4.5% |
| 30 | `runif` | stats | 413 | 4.4% |

## Top procedures, Python (n = 6233 parsed scripts)

| # | function | package | scripts | share |
|---|---|---|---|---|
| 1 | `randn` | numpy.random | 316 | 5.1% |
| 2 | `seed` | numpy.random | 252 | 4.0% |
| 3 | `RandomState` | numpy.random | 230 | 3.7% |
| 4 | `rand` | numpy.random | 223 | 3.6% |
| 5 | `randint` | numpy.random | 147 | 2.4% |
| 6 | `random` | numpy.random | 98 | 1.6% |
| 7 | `normal` | numpy.random | 84 | 1.3% |
| 8 | `uniform` | numpy.random | 73 | 1.2% |
| 9 | `choice` | numpy.random | 64 | 1.0% |
| 10 | `permutation` | numpy.random | 63 | 1.0% |
| 11 | `minimize` | scipy.optimize | 46 | 0.7% |
| 12 | `weibull` | numpy.random | 37 | 0.6% |
| 13 | `shuffle` | numpy.random | 32 | 0.5% |
| 14 | `LogisticRegression` | sklearn.linear_model | 31 | 0.5% |
| 15 | `LinearRegression` | sklearn.linear_model | 27 | 0.4% |
| 16 | `ols` | statsmodels | 24 | 0.4% |
| 17 | `default_rng` | numpy.random | 23 | 0.4% |
| 18 | `ppf` | scipy.stats | 22 | 0.4% |
| 19 | `cdf` | scipy.stats | 18 | 0.3% |
| 20 | `Ridge` | sklearn.linear_model | 16 | 0.3% |
| 21 | `OLS` | statsmodels | 15 | 0.2% |
| 22 | `root` | scipy.optimize | 15 | 0.2% |
| 23 | `Bounds` | scipy.optimize | 12 | 0.2% |
| 24 | `OptimizeResult` | scipy.optimize | 12 | 0.2% |
| 25 | `multivariate_normal` | numpy.random | 12 | 0.2% |
| 26 | `Lasso` | sklearn.linear_model | 11 | 0.2% |
| 27 | `pairwise_distances` | sklearn.metrics | 11 | 0.2% |
| 28 | `accuracy_score` | sklearn.metrics | 10 | 0.2% |
| 29 | `random_sample` | numpy.random | 10 | 0.2% |
| 30 | `rvs` | scipy.stats | 10 | 0.2% |

## Package exposure

Distinct scripts calling any inferential function of each package. Names
exported by more than one package count for each, so these are upper
bounds.

| package | script-calls | distinct functions |
|---|---|---|
| `raster` | 20242 | 219 |
| `Matrix` | 17855 | 137 |
| `memisc` | 10682 | 38 |
| `stats` | 6437 | 266 |
| `mice` | 2726 | 12 |
| `sp` | 2677 | 117 |
| `sf` | 2615 | 130 |
| `numpy.random` | 1746 | 55 |
| `srvyr` | 1509 | 54 |
| `rms` | 1095 | 15 |
| `zoo` | 770 | 26 |
| `fixest` | 457 | 43 |
| `scipy.stats` | 441 | 256 |
| `Hmisc` | 410 | 81 |
| `spdep` | 401 | 68 |
| `lfe` | 377 | 19 |
| `metafor` | 364 | 20 |
| `plm` | 280 | 16 |
| `scipy.optimize` | 274 | 126 |
| `xts` | 273 | 41 |
| `optmatch` | 247 | 5 |
| `nlme` | 245 | 63 |
| `lmtest` | 243 | 18 |
| `sandwich` | 238 | 21 |
| `MASS` | 223 | 40 |

## What the frame says

Random number generation dominates both languages: `rnorm` is the most
called procedure in R and `numpy.random` accounts for the whole Python
top ten. Any change to a generator or to how a seed is consumed moves
every simulation-based result in the corpus, which makes RNG the single
highest-exposure surface for changelog archaeology -- R 3.6.0's change to
`sample()` is the canonical example.

After simulation, the frame is concentrated: `lm` in 6.9% of R scripts,
then `glm`, then the robust-covariance family (`coeftest`, `vcovHC`,
`feols`, `lm_robust`) which is exactly where the cross-implementation
suite already finds a seven-fold disagreement between R and Python.

