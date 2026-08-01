# How far back this reaches

782 archived version(s) have been built against R 4.6.0; **316** succeeded.

Every backward-reaching measurement here -- screening a claim against the release before its fix, bisecting an introduction, sweeping a version history -- first has to install a decade-old source package against a current toolchain. Where that fails, the study stops, and the boundary is a property of today's compilers rather than of the package.

## Floors

| package | releases | tried | built | buildable | C/C++ | floor | reaches back to |
|---|---|---|---|---|---|---|---|
| `AER` | 32 | 2 | 2 | 100% | no | 1.2-5 | 2017-01-07 |
| `Hmisc` | 88 | 82 | 11 | 13% | yes | 4.6-0 | 2021-10-07 |
| `MASS` | 78 | 75 | 14 | 19% | yes | 7.3-58 | 2022-07-14 |
| `MatchIt` | 54 | 2 | 2 | 100% | yes | 4.3.4 | 2022-03-08 |
| `car` | 91 | 76 | 49 | 64% | no | 1.1-0 | 2006-02-06 |
| `estimatr` | 22 | 22 | 22 | 100% | yes | 0.2.0 | 2018-01-29 |
| `fixest` | 34 | 4 | 3 | 75% | yes | 0.9.0 | 2021-06-19 |
| `lfe` | 64 | 64 | 2 | 3% | yes | 3.1.0 | 2024-11-06 |
| `lme4` | 137 | 123 | 15 | 12% | yes | 0.96-1 | 2005-06-10 |
| `lmtest` | 46 | 36 | 24 | 67% | yes | 0.9-17 | 2006-08-12 |
| `mgcv` | 171 | 8 | 1 | 12% | yes | 1.8-42 | 2023-03-02 |
| `mice` | 50 | 2 | 2 | 100% | yes | 3.16.0 | 2023-06-05 |
| `plm` | 50 | 50 | 34 | 68% | no | 0.1-1 | 2006-06-12 |
| `psych` | 97 | 97 | 97 | 100% | no | 1.0-17 | 2007-05-06 |
| `randomForest` | 60 | 2 | 0 | 0% | yes | -- | -- |
| `sandwich` | 39 | 39 | 24 | 62% | no | 2.2-1 | 2009-02-05 |
| `sf` | 73 | 4 | 2 | 50% | yes | 1.0-0 | 2021-06-09 |
| `survival` | 109 | 94 | 12 | 13% | yes | 3.4-0 | 2022-08-09 |

Only versions this study actually asked for have been tried, so `tried` is not a sample of the history -- it is the set of releases some claim needed.

## The censoring is informative

Across packages with at least 8 releases tried, **compiled packages build 30% of the time** against **74% for pure R** (8 against 4 packages).

This is why the sweep sample stratifies on compiled code. The releases that cannot be observed are not missing at random: they are concentrated in exactly the packages whose C sources predate a change to R's API, and those are disproportionately the old, widely used ones. `lfe` is the sharpest case -- `felm` is the highest-reach function in the entire corpus at 245 scripts, and 62 of its 64 releases fail on `Calloc`, so the function that matters most has almost no measurable history. Averaging over that without saying so would report a bug rate for the packages that happen to compile and call it a bug rate for statistical software.

## Walls

| n | what stopped it |
|---|---|
| 27 | ./lme4CholmodDecomposition.h:20:45: error: no template named 'CholmodDecomposition' in namespace 'Eigen'; did you mean 'lme4CholmodDecomposition'? |
| 5 | ./predModule.h:30:17: error: no template named 'CholmodDecomposition' in namespace 'Eigen' |
| 1 | 144 | { error(_("An out of bound write to matrix has occurred!"),1); |
| 4 | ERROR: lazy loading failed for package ‘car’ |
| 25 | ERROR: lazy loading failed for package ‘lme4’ |
| 5 | Error in download.file(p, destfile, method, mode = "wb", ...) : |
| 6 | Error: Rank mismatch in argument 'work' at (1) (scalar and rank-1) |
| 16 | Hmisc.c:22:9: error: use of undeclared identifier 'PROBLEM' |
| 1 | MASS.c:446:21: error: use of undeclared identifier 'INT_MAX' |
| 4 | a C call whose R-internal signature has since changed |
| 1 | a C function declared implicitly, which current compilers reject |
| 43 | a dependency needing `S.h`, the S-PLUS header R deleted |
| 5 | a dependency that will not build either |
| 2 | a geospatial system library this machine does not have |
| 6 | documentation in an Rd syntax R no longer parses |
| 46 | no `NAMESPACE` file, which R has required since 2008 |
| 121 | the C sources call `Calloc`, renamed `R_Calloc` in R 4.2 |
| 3 | the C sources call `NAMED`, which R's API no longer exposes |
| 116 | the C sources use `Sint`, an S-PLUS typedef R no longer defines |
| 29 | the C++ sources use `DOUBLE_EPS`, a constant R has withdrawn |

**Building is not the only wall, and it is the one that announces itself.** `psych` 1.5.8 installs cleanly and then refuses to run: its own code says `if (class(x) == "try-error")`, which R has treated as an error since 4.2 when the condition has length greater than one. A package can therefore be buildable and unusable, so the floor above is a lower bound on how far back the archaeology reaches, never a promise.
