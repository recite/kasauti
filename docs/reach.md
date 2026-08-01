# How far back this reaches

88 archived version(s) have been built against R 4.6.0; **51** succeeded.

Every backward-reaching measurement here -- screening a claim against the release before its fix, bisecting an introduction, sweeping a version history -- first has to install a decade-old source package against a current toolchain. Where that fails, the study stops, and the boundary is a property of today's compilers rather than of the package.

## Floors

| package | releases | tried | built | floor | reaches back to |
|---|---|---|---|---|---|
| `AER` | 32 | 2 | 2 | 1.2-5 | 2017-01-07 |
| `MASS` | 78 | 1 | 0 | -- | -- |
| `MatchIt` | 54 | 2 | 2 | 4.3.4 | 2022-03-08 |
| `car` | 91 | 2 | 0 | -- | -- |
| `estimatr` | 22 | 4 | 4 | 0.4.0 | 2018-02-15 |
| `fixest` | 34 | 4 | 3 | 0.9.0 | 2021-06-19 |
| `lfe` | 64 | 2 | 0 | -- | -- |
| `lmtest` | 46 | 2 | 2 | 0.9-34 | 2015-06-06 |
| `mgcv` | 171 | 8 | 1 | 1.8-42 | 2023-03-02 |
| `mice` | 50 | 2 | 2 | 3.16.0 | 2023-06-05 |
| `plm` | 50 | 6 | 4 | 1.2-7 | 2011-02-06 |
| `psych` | 97 | 6 | 6 | 1.5.8 | 2015-08-30 |
| `randomForest` | 60 | 2 | 0 | -- | -- |
| `sandwich` | 39 | 18 | 18 | 2.2-1 | 2009-02-05 |
| `sf` | 73 | 4 | 2 | 1.0-0 | 2021-06-09 |
| `survival` | 109 | 23 | 5 | 3.4-0 | 2022-08-09 |

Only versions this study actually asked for have been tried, so `tried` is not a sample of the history -- it is the set of releases some claim needed.

## Walls

| n | what stopped it |
|---|---|
| 2 | a C call whose R-internal signature has since changed |
| 2 | a dependency that is no longer on CRAN |
| 2 | a geospatial system library this machine does not have |
| 4 | no `NAMESPACE` file, which R has required since 2008 |
| 4 | the C sources call `Calloc`, renamed `R_Calloc` in R 4.2 |
| 1 | the C sources call `NAMED`, which R's API no longer exposes |
| 3 | the C sources need gettext headers this machine does not have |
| 18 | the C sources use `Sint`, an S-PLUS typedef R no longer defines |
| 1 | the C++ sources use `DOUBLE_EPS`, a constant R has withdrawn |

**Building is not the only wall, and it is the one that announces itself.** `psych` 1.5.8 installs cleanly and then refuses to run: its own code says `if (class(x) == "try-error")`, which R has treated as an error since 4.2 when the condition has length greater than one. A package can therefore be buildable and unusable, so the floor above is a lower bound on how far back the archaeology reaches, never a promise.
