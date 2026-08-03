# kasauti

**कसौटी** — touchstone.

How often does statistical software quietly change your answer, how long does it
stay wrong, and would you find out from the changelog?

This runs a fixed battery of probes against **every release** of a package and
records each point where a number moved. The sampling unit is
`(package, release, probe)` — packages and probes chosen here, releases a census
— so the changelog becomes something to *check* rather than something to trust.
Where a changelog does claim a fix, the claim is tested against the release
before it; where a bug is confirmed, its own reproducer is driven down the
version history to date it.

Sibling to [recite/milaan](https://github.com/recite/milaan), which asks whether R
and Python agree *today*. That repository owns the comparison harness; running a
package against its own past self is the same machinery with *backend = version*
instead of *backend = language*.

---

## What we found

Every number here is reproduced by `make analysis` from the tables in `data/`.
Scale so far: **12 packages swept, 26 probes, 1,757 release-runs, 53 episodes**,
plus **470 reported issues** dated across the sampled packages that develop in the
open. Estimates run on the **designed sample** of 8; four swept packages entered
outside the draw and are reported separately, never pooled in.

### The past is gone

You mostly cannot run the software people actually ran.

| package | releases tried | built | buildable | C/C++ | history reaches back to |
|---|---|---|---|---|---|
| `psych` | 97 | 97 | **100%** | no | 2007-05-06 |
| `car` | 76 | 49 | 64% | no | 2006-02-06 |
| `estimatr` | 22 | 22 | **100%** | yes | 2018-01-29 |
| `MASS` | 75 | 14 | 19% | yes | **2022-07-14** |
| `Hmisc` | 88 | 17 | 19% | yes | 2021-10-07 |
| `survival` | 94 | 12 | 13% | yes | **2022-08-09** |
| `lme4` | 123 | 15 | 12% | yes | 2005-06-10 |
| `lfe` | 64 | 2 | **3%** | yes | **2024-11-06** |

**Compiled packages build 31% of tried releases against 74% for pure R.** `MASS`
ships *with R* and has 2,139 reverse dependencies, and its observable history
begins in **2022**. `lfe` — whose `felm` is the most-called function in the whole
corpus, 245 scripts — has one year. `survival` begins in 2022. Against `psych` and
`car`, both pure R, reaching 2006.

Not neglect: `Calloc` → `R_Calloc` in R 4.2, the `Sint` typedef, `NAMED`,
`DOUBLE_EPS`, `S.h`. Ordinary API hygiene, each decision reasonable, that
collectively closed the archive — and closed it *worst for the packages that
matter most*. That is a problem for anyone claiming to reproduce old analyses.

It is also why the sample stratifies on compiled code: the unobservable releases
are not missing at random, so averaging over them would report a bug rate for the
packages that happen to compile and call it a bug rate for statistical software.

A floor and a coverage are different facts and both travel. `lme4` has a 2005
floor and 12% coverage — one old release reachable, almost nothing between it and
now.

### Changelogs miss about two in five result changes

On the **designed sample**, 5 of 7 distinct `(package, release)` changes are named
in NEWS — **71%**, cluster bootstrap over packages **[54%, 100%]**. Pooling in the
packages that were swept but never drawn gives **14 of 21 (67%)**.

Those two are reported together because the pooled figure rests on packages the
draw did not choose. `psych`, `estimatr`, and `survival` have fixtures from the
earlier screening pass, so they entered by *having a shortlisted changelog
entry* — selection on having a documented bug. That was expected to push the
pooled share **above** the designed one. It does not. With seven designed changes
the two cannot be told apart, and the prediction is recorded as refused rather
than quietly dropped.

It is a **lower bound**: the flag counts a match on any function a probe declares,
which biases it toward "documented". And documented is not the same as noticed —
see the singleton case below, which is in NEWS in detail and still cost a day.

And this quantity is not estimable from inside a changelog-first design at any
sample size — an undocumented change is exactly what such a design cannot see.
That is what forced the sampling unit to change.

### Bugs that survive, survive long

Median episode length **2613 days** by the Turnbull estimate; longest observed
span 5671 days; about **0.08 changes per probe-year**. The Weibull scale is 1.64,
so the hazard *decreases* with duration: old code is stable code — and a bug that
makes it past its first year is likely good for a decade.

### Almost all of a bug's life is spent undiscovered, not unfixed

Once somebody reports a defect, it is fixed fast: **median 55 days** from issue
to release, cluster bootstrap over packages **[32, 105]**, from 470 resolved
citations. By package: `spdep` 30, `brms` 54, `plm` 92, `lme4` 107, `rms` 225.

Set that beside a median episode length of **2613 days**. The two are not the
same bugs — one is 470 reported issues across the packages that develop in the
open, the other 27 closed episodes across twelve swept packages — so this is a
comparison of distributions, not a decomposition. But a **47× gap** is not a
sampling artifact.

**Maintainers are not slow. Discovery is the bottleneck.** Effort spent making
bugs easier to *find* buys far more than effort spent making them faster to fix.

This estimand carries a gate the others do not: **12 of the 26 sampled packages
name no GitHub repository on CRAN** — `MASS`, `sandwich`, `lmtest`, `Hmisc` among
them. Packages that develop in the open are not a random half of the frame, so
every latency here is conditional on a development practice.

### Half the biggest packages never moved at all

Four of the eight certainty-stratum packages produced no change on their
most-called functions: `MASS` (3 probes across 14 observable releases), `lme4`
(2/11), `Hmisc` (1/17), `lfe` (2/2). Mature software is genuinely mature. That is
worth as much as a change would be — and it is only interpretable because the
observable-release count travels beside it. "No change in 14 releases" and "no
change in 2" are different claims.

---

## The bugs

### Verified by running both versions against the same bytes

| bug | what moved |
|---|---|
| `lfe` before 2.5 | two-way clustered SE understated **5.78×**; t goes 83.0 → 14.4, coefficients identical |
| `sandwich` 2.5-0 | `vcovHC.mlm` cross-equation covariances — signs flipped, one off by 33×. Wrong **8.7 years**, and it arrived *with* the feature: 2.2-3 has no `mlm` method at all |
| `fixest` 0.10.3 | extracted fixed effects miss the fit by **3.37** across four dimensions — they fail their own defining identity, so the case adjudicates itself |
| `scikit-learn` 1.0.2 | `normalized_mutual_info_score` returns **1.25** from a metric bounded on [0, 1] |
| `lmtest` 0.9-35 | `bptest` counted an aliased regressor in its degrees of freedom: df **3 → 2**, p-value with it, statistic untouched. Lived 3220–3836 days |
| `psych` 1.9.12 | **all twelve** `ICC` confidence bounds moved; every point estimate unchanged |
| `sandwich` 3.0-2 | cluster-robust HC2 on a glm off by 4.7e-3; 7 of 9 quantities bit-identical, which confines it to the documented conditions |
| `mgcv` 1.9-0 | **NOT_REPRODUCED** — a recorded failure. The entry reads accurate; the reproducer did not reach it |

### The singleton case: a change no coefficient comparison could find

A regression table disagreed with itself across machines on a live analysis:
7,188 → 7,082 observations, 465 → 359 parties, 54 → 53 clusters. Not the data —
`fixest` changed what it does with **singleton fixed effects**, levels holding
exactly one observation. Three answers were available and no two agreed:

| source | says |
|---|---|
| recollection | `fixest` ≥ **0.12** drops them |
| `fixest` NEWS | the default changed in **0.13.0** |
| CRAN | never shipped 0.13.0 — the archive goes 0.12.1 → 0.13.2 |

Running it settles it. A probe on 260 rows over 60 groups, 20 of them singletons:

| version | `nobs` | groups kept | `se.x1` |
|---|---|---|---|
| 0.9.0 … 0.12.1 | 260 | 60 | 0.0326176876869212 |
| 0.13.2 … 0.14.2 | **240** | **40** | 0.0326556638110313 |

The changelog was right and the recollection was one minor version early: 0.12.0
and 0.12.1 keep singletons, and 0.13.2 is the first release that drops them.

**And the coefficients never moved.** `coef.x1` is 1.60144801573067 in every
version on both sides of the transition. That is not luck — a singleton is
perfectly fit by its own dummy, so it carries no identifying variation and cannot
move a point estimate. What it carries is a parameter. Removing it changed the
observation count, the fixed-effect parameter count (66 → 46), and therefore
**the standard errors**.

So the obvious probe — fit the model, compare the coefficients — returns *no
change* and is wrong. The change is invisible in the estimates and plain in the
sample. Every probe should report `nobs` and the groups it retained before it
reports a coefficient, because `N` moving 7,188 → 7,082 is legible on sight and
"a standard error moved 0.1%" is the same event described uselessly.

**Documented is not noticed.** This change is in NEWS, in detail, with the
replacement argument named. It still cost a day, because nobody re-reads a
changelog on upgrade. `E2` measures whether a change is *described*; it does not
measure whether anyone found out.

`fixest` was **not drawn** in the sample — it is here because a bug was found in
it, which is selection on the outcome — so it carries the `case-study` stratum,
weight 0, and is excluded from every estimate. A test asserts that.

### Changes nobody wrote down

The sweep's own catch — real movements, silent NEWS:

| change | magnitude | lived |
|---|---|---|
| `plm` 1.3-1, `pgmm` instrument lags | relative **1.00** — the coefficient changed completely | 454–676 days |
| `psych` 1.0-83, `alpha`'s standard error | 0.875 | 192–260 days |
| `plm` 1.4-0, `pgmm` / `mtest` | 0.500 | 0–380 days |
| `psych` 2.4.1 and 2.2.9, `alpha` under missing data | 7.5e-3, 3.0e-3 | 447–1014 days |
| `estimatr` 0.6.0 | with weights *and* blocks, 0.4.0 returned **no standard error and no p-value at all** — they do not change, they *appear* | — |
| `car` 2.1-3 | `deltaMethod` began returning confidence intervals where 2.1-2 returned none | — |

The `plm` one is the most concerning: a GMM coefficient that changed completely,
in a panel estimator, with no changelog entry.

Cross-language findings — Newey–West differing 7×, `sklearn`'s silent L2, the NIST
Longley digit counts — live in [milaan](https://github.com/recite/milaan) with the
harness.

---

## How it works

**A sweep** runs each probe against every dated release and reports where a number
moved. Three rules make the encoding honest, each asserted by test:

- **A gap is not a data point.** A release that will not build, or builds and
  refuses to run, breaks the chain; each observed release is compared against the
  last *observed* one. Treating a gap as "no change" manufactures stability out of
  a build failure.
- **A duration is an interval.** `lower_days` is what certainly elapsed,
  `upper_days` what may have — never a midpoint nobody observed.
- **A birth is not a censoring.** When the releases before the first observation
  failed because the *code did not exist*, the episode has a start date.

**The sweep recovers the bisect by an entirely different route.** Driven down a
binary search, `sandwich`'s reproducer said: introduced 2.2-4, fixed 2.5-0,
arrived with the feature. The sweep knows none of that — it runs a generic probe
across all 39 releases, finds **exactly one change point in the whole history**,
and yields an episode of **[2788, 3175] days** whose upper bound is exactly the
bisect's 8.7 years.

**A screen** is the cheap tier: one fixture against the release that carried a
claimed fix and the release before it, asking only whether a number moved. No
prose, no expectations. Only a screen that moves something is promoted to a full
record. Of **13 claims screened**: 5 moved a number, 4 did not, 4 could not be
evaluated. `docs/screening.md` has the table.

**Statistics.** `analysis/estimands.R`, base R plus `survival` only, so re-running
them needs no dependency resolver. Interval-censored throughout. Clustering by
package is handled three ways deliberately: rates averaged over packages rather
than pooled over episodes, a cluster bootstrap over packages for the documented
share, and package effects in the duration model.

The full argument for every choice above is in **[`docs/method.md`](docs/method.md)**.

---

## The design

**Which packages.** Sweeping is expensive, so the draw is stratified, seeded, and
recorded: `data/frame/sample.csv` carries every package's inclusion probability
and Horvitz–Thompson weight. Two stratifiers — usage, with the top 8 a certainty
stratum at probability 1; and compiled code, because it is the strongest predictor
of whether a release builds at all. **26 packages, 1,347 releases, weights 1.0 to
8.7.**

**Which functions.** A package's battery is its most-called exported functions in
the corpus, not a hand-picked list, with base-R names shadowed, non-computing
names excluded, and contested names apportioned between owners. Coverage is then a
number rather than a hope: `lfe` 80%, `lmtest` 66%, `sandwich` 56%, `Hmisc` 16%.

**The frame those are drawn from** covers **131 R packages** — CRAN Task Views ∩
corpus usage, an intersection of two external sources rather than anyone's memory.
`docs/sampling-frame.md` and `docs/method.md` argue it.

**Usage, three ways.** Corpus archives answer *which published paper could this
have reached*, and are field-specific by construction. `kasauti frame usage` adds
CRAN reverse dependencies and downloads, which are not. They disagree: Spearman
between corpus rank and reverse-dependency rank is **0.32**, against **0.88**
between the two CRAN-wide measures. `lfe` is seventh in the corpus and has four
reverse dependencies — invisible to any frame built on ecosystem centrality.

---

## What every number is conditional on

Six gates, each a column somewhere rather than a caveat in prose, and **all of
them push the same way** — toward shorter measured lifetimes and fewer detected
changes.

| gate | where it is visible |
|---|---|
| **buildability** — an unbuildable release cannot be observed | `data/builds.csv`; `gaps` in `changes.csv`; `LEFT_CENSORED` in `episodes.csv` |
| **runnability** — a release can build and still refuse to run | `GAP` observations in `sweeps/*/*.json`, with the R error |
| **probe coverage** — a change no probe exercises is invisible | `data/frame/batteries.csv` |
| **documentation** — NEWS may not mention a change | `closed_documented`; this is the estimand, not an assumption |
| **eventual change** — a value still holding may be wrong and undiscovered | `RIGHT_CENSORED`; these are never dropped |
| **open development** — a package with no public tracker has no report date | `data/flagged.csv`, 14 of 26 sampled packages |

`docs/reach.md` groups every recorded build failure by its cause.

---

## Reproducing it

```
bugs/<language>/<package>/<version-slug>/   one directory per verified bug
fixtures/<package>/                          probe data and scripts
screens/<package>/                           one JSON per screened claim
sweeps/<package>/                            one timeline per (package, probe)
data/                                        the released tables
analysis/estimands.R                         the statistics
docs/                                        method, reach, screening, dashboard
```

```bash
make install
make data            # rebuild every derived table
make analysis        # the four estimands, in R
make check           # lint, types, tests

kasauti frame sample     # draw the stratified package sample
kasauti frame battery    # propose probes from corpus call volume
kasauti sweep <package>  # run every probe against every release
kasauti episodes         # durations, with their censoring
kasauti build audit      # how far back each package still installs
kasauti screen run       # test a changelog claim against the release before it
kasauti flagged          # date changelog issue citations from GitHub
kasauti bug bisect <id>  # date a confirmed bug by running old versions
kasauti run --all --strict   # re-verify every bug record
```

Sweeps are deliberately **not** a `make` target: they take hours, they are the
only stage touching the network and the compiler, and they are keyed by package.
Everything downstream rebuilds from `sweeps/` in seconds — so a reader can redo
the statistics without redoing the compute.

`data/dictionary.md` documents every column of every released table;
`data/manifest.json` carries each table's SHA-256, byte count, and row count, so a
claim traces to what it was computed from.

---

## Limits

**The sample is not yet the population.** 19 changes across 11 packages. Eight of
those are the certainty stratum, which is complete; the 18 sampled-stratum
packages carry the weights (4.7–8.7) that would turn these counts into population
estimates, and they are not swept yet.

**Right-censoring is heavy enough to break an interval.** Zero of 1000 cluster
resamples reached a median episode length, and the analysis says so rather than
omitting it.

**Package as a fixed effect, not a frailty.** `survreg` implements no frailty
term, `coxph` takes no interval censoring, and a variance component from eleven
clusters would be barely identified. A random effect becomes the right tool when
the package count grows, not before.

**Discovery latency is inferred, not measured.** Report-to-release is measured
directly; introduction-to-report is the gap between two distributions estimated on
different samples. Closing that properly needs an introduction date and a report
date for the *same* bug, which currently exists for a handful of records.

**Changelogs are self-reported.** `survival` documents 114 versions meticulously;
`MASS` has no version structure at all. **27 of the 131 selected packages ship no
machine-readable changelog whatsoever.** Raw bug counts across packages measure
candor at least as much as bugginess, which is the substantive reason the sweep
exists.

**The classification tail is unread, not cleared.** Every changelog entry is judged
by hand, so the queue is finite: **207 of 369** exposed entries are read, worked in
descending exposure, and nothing in the unjudged 162 touches more than 25 corpus
scripts. A bug sitting in that tail has not been ruled out; it has not been looked
at.

**Python coverage is bounded by the corpus, not by the selection.** Of 6,233 parsed
Python scripts the inferential imports are `numpy` (2,914), `scipy` (881), `sklearn`
(254), and `statsmodels` (46). R's `lm` alone appears in 643 — an order of magnitude
more than all of statsmodels. And R packages export *procedures* (nothing but
`sandwich` means `vcovHC`), while numpy exports *primitives*, so a Python calling
count is a technically-true upper bound carrying almost no information.

**Publication date is a weak proxy for when an analysis was run**, in both
directions. One archive here went up six weeks *after* the fix that would have
affected it.
