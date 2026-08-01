# How far back this reaches

429 archived version(s) have been built against R 4.6.0; **227** succeeded.

Every backward-reaching measurement here -- screening a claim against the release before its fix, bisecting an introduction, sweeping a version history -- first has to install a decade-old source package against a current toolchain. Where that fails, the study stops, and the boundary is a property of today's compilers rather than of the package.

## Floors

| package | releases | tried | built | buildable | C/C++ | floor | reaches back to |
|---|---|---|---|---|---|---|---|
| `AER` | 32 | 2 | 2 | 100% | no | 1.2-5 | 2017-01-07 |
| `MASS` | 78 | 1 | 0 | 0% | yes | -- | -- |
| `MatchIt` | 54 | 2 | 2 | 100% | yes | 4.3.4 | 2022-03-08 |
| `car` | 91 | 2 | 0 | 0% | no | -- | -- |
| `estimatr` | 22 | 22 | 22 | 100% | yes | 0.2.0 | 2018-01-29 |
| `fixest` | 34 | 4 | 3 | 75% | yes | 0.9.0 | 2021-06-19 |
| `lfe` | 64 | 64 | 2 | 3% | yes | 3.1.0 | 2024-11-06 |
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

Across packages with at least 8 releases tried, **compiled packages build 39% of the time** against **77% for pure R** (5 against 3 packages).

This is why the sweep sample stratifies on compiled code. The releases that cannot be observed are not missing at random: they are concentrated in exactly the packages whose C sources predate a change to R's API, and those are disproportionately the old, widely used ones. `lfe` is the sharpest case -- `felm` is the highest-reach function in the entire corpus at 245 scripts, and 62 of its 64 releases fail on `Calloc`, so the function that matters most has almost no measurable history. Averaging over that without saying so would report a bug rate for the packages that happen to compile and call it a bug rate for statistical software.

## Walls

| n | what stopped it |
|---|---|
| 1 | 144 | { error(_("An out of bound write to matrix has occurred!"),1); |
| 1 | Error in download.file(p, destfile, method, mode = "wb", ...) : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/Rtmp3KfiWu/R.INSTALLabae4f0df16/sandwich/man/vcovHAC.Rd", : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/RtmpGyjbGV/R.INSTALLabdf2973e292/sandwich/man/vcovHAC.Rd", : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/RtmpMJonOl/R.INSTALLab78317373b8/sandwich/man/vcovHAC.Rd", : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/RtmpZ9DgZJ/R.INSTALLab441a6f5c2b/sandwich/man/vcovHAC.Rd", : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/RtmpeTIkgr/R.INSTALLab0f238aa976/sandwich/man/vcovHAC.Rd", : |
| 1 | Error in parse_Rd("/private/var/folders/ks/1g8bn5m566n_w4l5hwwjv4180000gn/T/RtmpmnsrFO/R.INSTALLaade389c9f4f/sandwich/man/vcovHAC.Rd", : |
| 4 | a C call whose R-internal signature has since changed |
| 23 | a dependency that is no longer on CRAN |
| 2 | a geospatial system library this machine does not have |
| 1 | lfe.c:369:27: error: call to undeclared function 'sem_timedwait'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration] |
| 25 | no `NAMESPACE` file, which R has required since 2008 |
| 78 | the C sources call `Calloc`, renamed `R_Calloc` in R 4.2 |
| 3 | the C sources call `NAMED`, which R's API no longer exposes |
| 57 | the C sources use `Sint`, an S-PLUS typedef R no longer defines |
| 1 | the C++ sources use `DOUBLE_EPS`, a constant R has withdrawn |

**Building is not the only wall, and it is the one that announces itself.** `psych` 1.5.8 installs cleanly and then refuses to run: its own code says `if (class(x) == "try-error")`, which R has treated as an error since 4.2 when the condition has length greater than one. A package can therefore be buildable and unusable, so the floor above is a lower bound on how far back the archaeology reaches, never a promise.
