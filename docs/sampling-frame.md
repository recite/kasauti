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

## How a call is attributed to a package

**R.** A name is attributed to every installed package in the curated
list that exports it, established by `getNamespaceExports` rather than by
a hand-written table. Names the tidyverse routinely masks -- `filter`,
`select`, `lag`, `slice` -- count only when written `pkg::name`, since a
bare `filter()` in a script that loads dplyr is dplyr's. That rule
discarded 2444 script-function pairs, which is the
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

Not introspectable (not installed, so unattributable): `rddtools`.

## Top procedures, R (n = 9343 parsed scripts)

| # | function | package | scripts | share |
|---|---|---|---|---|
| 1 | `rnorm` | stats | 690 | 7.4% |
| 2 | `lm` | stats | 643 | 6.9% |
| 3 | `quantile` | stats | 420 | 4.5% |
| 4 | `runif` | stats | 413 | 4.4% |
| 5 | `sd` | stats | 343 | 3.7% |
| 6 | `glm` | stats | 206 | 2.2% |
| 7 | `pnorm` | stats | 188 | 2.0% |
| 8 | `median` | stats | 185 | 2.0% |
| 9 | `coeftest` | lmtest | 120 | 1.3% |
| 10 | `feols` | fixest | 117 | 1.3% |
| 11 | `qnorm` | stats | 117 | 1.3% |
| 12 | `cor` | stats | 116 | 1.2% |
| 13 | `var` | stats | 114 | 1.2% |
| 14 | `weighted.mean` | stats | 103 | 1.1% |
| 15 | `dnorm` | stats | 99 | 1.1% |
| 16 | `optim` | stats | 85 | 0.9% |
| 17 | `vcovHC` | plm;sandwich | 76 | 0.8% |
| 18 | `rbinom` | stats | 74 | 0.8% |
| 19 | `style.tex` | fixest | 69 | 0.7% |
| 20 | `pt` | stats | 67 | 0.7% |
| 21 | `model.response` | stats | 66 | 0.7% |
| 22 | `pchisq` | stats | 66 | 0.7% |
| 23 | `anova` | stats | 64 | 0.7% |
| 24 | `index` | plm | 59 | 0.6% |
| 25 | `rq` | quantreg | 58 | 0.6% |
| 26 | `dist` | stats | 55 | 0.6% |
| 27 | `lm_robust` | estimatr | 55 | 0.6% |
| 28 | `mvrnorm` | MASS | 54 | 0.6% |
| 29 | `t.test` | stats | 54 | 0.6% |
| 30 | `ts` | stats | 53 | 0.6% |

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
| `stats` | 6437 | 266 |
| `numpy.random` | 1746 | 55 |
| `fixest` | 457 | 43 |
| `scipy.stats` | 441 | 256 |
| `plm` | 280 | 16 |
| `scipy.optimize` | 274 | 126 |
| `nlme` | 245 | 63 |
| `lmtest` | 242 | 17 |
| `sandwich` | 238 | 21 |
| `quantreg` | 238 | 61 |
| `MASS` | 223 | 40 |
| `sklearn.metrics` | 208 | 102 |
| `sklearn.linear_model` | 191 | 74 |
| `lme4` | 186 | 26 |
| `VGAM` | 164 | 30 |
| `survival` | 161 | 14 |
| `estimatr` | 102 | 12 |
| `mgcv` | 91 | 16 |
| `car` | 70 | 14 |
| `statsmodels` | 63 | 13 |
| `MatchIt` | 59 | 4 |
| `pscl` | 51 | 7 |
| `metafor` | 49 | 7 |
| `AER` | 44 | 4 |
| `multiwayvcov` | 28 | 1 |

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

