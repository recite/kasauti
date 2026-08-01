# kasauti

**कसौटी** — touchstone.

Package changelogs are a confession log. This mines them for fixes that changed
results, works out when each bug was live, and traces it to the published
replication archives that called the affected function during that window.

Then it runs the buggy version and the fixed version against the same data and
reports what actually moved — because a changelog entry is a claim, and a claim
about a wrong number is worth exactly as much as the number that proves it.

Sibling to [recite/milaan](https://github.com/recite/milaan), which asks the other
question: do R and Python agree *today*. That repository owns the comparison
harness, and this one depends on it — verifying a bug means running one package
against its own past self, which is the same machinery with *backend = package
version* instead of *backend = language*.

## What it has found

Every number below was measured by running the thing, not predicted.

| finding | |
|---|---|
| `lfe` before 2.5 understated a clustered standard error **5.78×** | two-way clustering with a non-PSD CGM covariance; t goes 83.0 → 14.4, coefficients identical |
| `sandwich` 2.5-0 flipped the sign of cross-equation covariances | verified against 2.4-0; within-equation blocks bit-identical |
| `fixest` 0.10.3's extracted fixed effects miss the fit by **3.37** | four dimensions; they fail their own defining identity, so the case adjudicates itself |
| `sandwich` 3.0-2 moved cluster-robust HC2 on a glm by 4.7e-3 | 7 of 9 measured quantities bit-identical, which confines it to the documented conditions |
| `scikit-learn` 1.0.2 returns **1.25** from a metric bounded on [0, 1] | `normalized_mutual_info_score`, `average_method` of `min` or `geometric` |
| `mgcv` 1.9-0's multinomial variance fix — **NOT_REPRODUCED** | a recorded failure; the lead did not survive execution |

Cross-language findings — Newey–West differing 7×, `sklearn`'s silent L2, the NIST
Longley digit counts — moved to [milaan](https://github.com/recite/milaan) with the
harness.

## Layout

```
bugs/<language>/<package>/<version-slug>/    one directory per bug
data/                        harvested changelogs, the frame, classifications
docs/                        the dashboard published to GitHub Pages
```

A bug belongs to exactly one package in exactly one language, so that is the
directory tree. Papers and impact are not hierarchies — one paper is hit by many
bugs and one bug hits many papers — so they are **generated views** rather than
directory levels:

```
bugs/INDEX.md        by impact: severity x narrowed exposure
bugs/BY-PAPER.md     inverted: per archive, which bugs reach it
bugs/findings.csv    one row per bug: language, package, exposure, status, magnitude
bugs/findings.json   the same, plus per-archive detail
```

A bug directory that has reached verification contains a `case.yaml`, so it is
discovered by milaan's runner like any other comparison. The lifecycle falls out of
the files.

## Which packages, and why not the ones I remembered

The frame covers **131 R packages**, chosen by intersecting two sources, neither of
them my judgment: the packages CRAN's expert-maintained [Task
Views](https://cran.r-project.org/web/views/) list for a field, and the packages
replication archives in the corpus actually load. A package qualifies by being both
recognized by the field and used in the literature — 28 relevant views list 3,509
packages, of which 131 appear in at least 10 corpus archives.

The first version of this frame named 15 packages from memory. Measuring the corpus
afterwards showed what that costs. `lfe` — Simen Gaure's fixed-effects estimator,
loaded by **222 archives** — had simply been forgotten, and its changelog turned out
to hold the single most-exposed candidate in the study: a change to how multiway
clustered standard errors handle negative eigenvalues, touching 245 scripts. A
package left off a hand-written list is indistinguishable from a package with
nothing wrong.

Judgment survives in two exclusion rules, both stated at the level of a category
rather than a package, and both falsifiable in a way an inclusion list is not:

- **`INFERENTIAL_VIEWS`** — which of CRAN's 49 views describe inference rather than
  software infrastructure, presentation, or a distant laboratory domain.
- **`NON_INFERENTIAL`** — packages whose whole job is plotting, formatting, or data
  manipulation. Unavoidable, because `ggplot2` is genuinely part of the Spatial and
  NetworkAnalysis toolkits, so no choice of views excludes it.

Cast wide at the package level, filter narrow at the function level. `broom` is the
proof: it is mostly extraction, `tidy` and `glance` are already excluded as
non-computing, and so it contributes almost nothing — without anyone having to
decide that it should.

**Exports come from the tarball, not from an install.** Attribution used to ask a
running R session `getNamespaceExports(pkg)`, which meant a package had to build on
this machine to be studied — and that build ceiling, not any principle, was what
capped the study at 15 packages. The `NAMESPACE` file sits inside the source tarball
already being downloaded for `NEWS`, so both come out of one read. Checked against
the installed namespaces it replaces, the parse loses **2 names across 28 packages**,
both traceable to a version difference rather than to the parser.

**A name someone else owns counts only when qualified.** Two rounds of this, both
found by checking a suspiciously large number rather than by reasoning:

- `Matrix` exports `diag`, `head`, `crossprod`, and `rowMeans`. Counting every bare
  `diag()` put `Matrix` at the top of the queue on **3,562 scripts** that meant base
  R's, burying `lfe` at 245.
- `alpha` is Cronbach's alpha in `psych` and colour transparency in `scales`. In
  this corpus it is written `scales::alpha` **eight** times against `psych::alpha`
  **six** — so seven `psych` entries reached the shortlist at 43 scripts on the
  strength of ggplot2 code. Corrected, they sit at 6.

So the shadow set is base R **plus the non-inferential packages**, computed from
their NAMESPACEs rather than listed. Nothing is lost by shadowing the second group:
they are precisely the packages already excluded for not computing anything, so a
name they own has no business being credited to a package that does. `car`'s
`recode` entry, which is `dplyr`'s `recode` in the corpus, fell from 46 to 2 the
same way.

One collision this does not catch, recorded because it is still live: `psych`'s ICC
entry reads "confidence intervals were incorrectly based upon alpha/2", and the
`alpha` there is a significance level, not `psych::alpha`. `ICC` itself is called by
**zero** corpus scripts, so that entry's real exposure is nil. Matching identifiers
cannot tell a function name from a statistical symbol spelled the same way.

## How long was it wrong

A bug's lifetime cannot be read off the corpus. Of 369 exposed changelog entries,
**four** name the version that introduced the defect and eleven call themselves
regressions — so the left edge of every exposure window here starts out censored.
The only way to get a real date is to run the code.

`kasauti bug bisect` drives a verified record's own reproducer against archived
CRAN versions and asks which of its two recorded outputs the run matches. No new
oracle is needed: `results.buggy.json` and `results.fixed.json` were written when
the bug was verified.

**`sandwich`'s `vcovHC.mlm` sign error was wrong for 8.7 years** — introduced in
2.2-4 (2009-12-07), fixed in 2.5-0 (2018-08-17), 31 releases apart. And it arrived
*with* the feature: 2.2-3 has no `mlm` method at all. Nobody broke it; it was
wrong when written, which is a different claim from a regression and is recorded
as one.

Four outcomes per probe, not two. `ABSENT` — the code does not exist in this
version — is the one that matters: a bug in a method nobody has written is not a
bug, and it bounds the search from below exactly as a working version would.
Before that distinction existed, the same bisect tested 19 versions and gave up;
with it, five probes settle the question.

`UNEVALUABLE` stays separate from both. The old end of a version range is where
things stop building, and collapsing "cannot tell" into "not buggy" would date
every introduction to the last version that happened to compile.

Three of four bisects did not bracket, each stopped by a different wall, and the
walls are the finding:

| record | result | what stopped it |
|---|---|---|
| `sandwich` 2.5-0 | **8.7 years**, bracketed | — |
| `sandwich` 3.0-2 | at least 4.9 years | its reproducer wraps calls in `try(silent = TRUE)`, so "not implemented" and "broken" look identical |
| `fixest` 0.10.4 | at least 0.8 years | templated C++ before mid-2021 will not compile against a current toolchain |
| `plm` 1.5-13 | nothing | the changelog does not date 1.5-13, so there is no timeline to place anything on |

An unbracketed bisect still yields a floor, and the floor is reported — but it is
deliberately *not* written into `introduced_on`. Closing the window at a date the
bug may predate would narrow it, and a window that is too narrow hides papers
rather than over-counting them.

## The sampling unit, and why it changed

A changelog entry exists only if someone **noticed** a bug, **fixed** it, and
**wrote it down**. Every duration computed from that frame is conditional on all
three, and the conditioning is invisible in the answer. Worse, five separate
gates — documentation, eventual fixing, buildability, probe reachability, and
working in descending exposure — all push the same way, toward *shorter* measured
lifetimes. A number produced that way is a lower bound wearing the clothes of an
estimate.

So the instrument changed. A **sweep** runs a probe against *every release* of a
package and reports each point where a number moved. The unit becomes
`(package, release, probe)` — packages and probes chosen here, releases a census
within package — and the changelog drops to a **label layer**. "What fraction of
result-changing releases does NEWS document?" stops being an assumption and
becomes `closed_documented`.

**The sweep recovers the bisect by an entirely different route.** Driven down a
binary search, `sandwich`'s reproducer said: introduced 2.2-4, fixed 2.5-0,
arrived with the feature. The sweep knows none of that — it runs a generic probe
across all 39 releases. It finds **exactly one change point in the whole history**,
at 2.5-0 immediately after 2.4-0, with no gap inside the interval; 2.2-4 is the
oldest evaluable release; and 2.2-1 through 2.2-3 are gaps whose recorded reason
is "no applicable method for `vcovHC`". The resulting episode is
**[2788, 3175] days**, and 3175 is exactly the bisect's 8.7 years.

Three rules make the encoding honest, and each is asserted by test:

- **A gap is not a data point.** A release that will not build, or builds and
  refuses to run, breaks the chain; each observed release is compared against the
  last *observed* one. Treating a gap as "no change" manufactures stability out of
  a build failure; treating it as a value puts a change point at every toolchain
  wall.
- **A duration is an interval.** `lower_days` is what certainly elapsed,
  `upper_days` what may have. Where a build failure sits inside a bounding
  interval the two differ, and the model is told rather than handed a midpoint
  nobody observed.
- **A birth is not a censoring.** When the releases before the first observation
  failed because the *code did not exist*, the episode has a start date. Same
  distinction `ABSENT` taught the bisect, third time it has paid.

`data/dictionary.md` documents every column; `data/manifest.json` carries each
table's hash. `analysis/estimands.R` computes the estimands in base R plus
`survival` alone, so re-running the statistics needs no dependency resolver.
Clustering by package is handled three ways on purpose — rates averaged over
packages rather than pooled over episodes, a cluster bootstrap over packages for
the documented share, and a package frailty term in the duration model, because a
frailty leans on a parametric random effect a bootstrap does not.

## Which packages get swept

Sweeping is the expensive stage — a whole release history, one build each — so
which packages are swept is a sampling decision, and made badly it repeats a
mistake this project has already made twice (a frame named from memory, a queue
worked in descending exposure). `kasauti frame sample` draws it **stratified,
seeded, and recorded**: `data/frame/sample.csv` carries every package's inclusion
probability and Horvitz–Thompson weight.

Two stratifiers, neither aesthetic:

- **Usage**, with the top 8 a **certainty stratum** taken at probability 1. A
  study of statistical software that sampled away `MASS` is answering a different
  question.
- **Compiled code**, because it is the strongest available predictor of whether a
  release builds at all. Every wall in `docs/reach.md` but one is a C or C++
  symbol; `survival` at 12 of 94 reachable is the case that makes this necessary
  rather than tidy. Sampling without it risks a draw that is mostly unbuildable,
  and the shortfall would read as a finding about bug rates.

The draw is **26 packages, 1347 releases**, weights 1.0 to 8.7. The three already
swept (`sandwich`, `lmtest`, `plm`) all fall in the certainty stratum, which a
test asserts — a design that excluded already-measured packages would waste them.

## What the first sweep measured

Six packages, 14 probes, **851 release-runs**: 38 episodes, 24 of them closed.
`make analysis` reproduces every number; `docs/estimands.txt` is its output.

**About two in five result-changing releases are not described in the changelog.**
Collapsing probe-level detections to the release — two `estimatr` probes call the
same function, so one event was being counted twice — gives **11 of 18 documented
(61%)**, cluster bootstrap over packages **[54%, 86%]**. That share is not
estimable from inside a changelog-first design at all: an undocumented change is
exactly what such a design cannot see.

**Result changes are rare per release and long-lived when they happen.** About
**0.15 changes per probe-year**. Median episode length **1109 days** by the
Turnbull estimate, longest observed span 5394 days. A Weibull AFT puts the scale
at **1.68** — hazard *decreasing* in duration, so the longer a value has held the
less likely it is to change next. Package fixed effects are jointly
indistinguishable from zero (χ² = 7.19 on 5 df, p = 0.21), which at 38 episodes
is what honesty looks like rather than evidence packages are alike.

**Four of 24 changes are a quantity appearing or vanishing**, not moving —
`estimatr` 0.6.0 began returning a standard error where 0.4.0 returned nothing.
Those carry `max_reldiff = 0`, so they are counted apart rather than dragging the
magnitude summary toward zero. Of the 20 numeric changes, **13 moved a number by
more than 1%**.

Three limits stated in the same breath, because they all cut the same way:

- **Coverage varies enormously.** `psych` and `estimatr` are fully buildable;
  `survival` is **12 of 94 releases (13%)**, so its one episode is nearly all the
  history that can be seen.
- **Right-censoring is heavy enough to break an interval.** Zero of 1000 cluster
  resamples reached a median, and the script says so instead of omitting it.
- **Package as a fixed effect, not a frailty.** `survreg` implements no frailty
  term, `coxph` takes no interval censoring, and a variance component from six
  clusters would be barely identified anyway. A random effect becomes the right
  tool when the package count grows, not before.

## Usage, measured three ways

Corpus exposure answers *which published paper could this bug have reached*, and
it is field-specific by construction. `kasauti frame usage` adds two measures that
are not: CRAN reverse dependencies, and downloads over a fixed cached window.

They disagree, which is the point. Spearman correlation between corpus rank and
reverse-dependency rank is **0.32**; between the two CRAN-wide measures, **0.88**.
So the ecosystem measures agree with each other about centrality and say almost
nothing about use in one field. `lfe` is the case in point — seventh most used
package in the corpus, **four** reverse dependencies on all of CRAN, invisible to
any frame built on centrality. It is the same package this README already records
as having been forgotten when the frame was built from memory.

## Screening: testing a claim without committing to publishing it

Seven records stood against a shortlist of **41** entries the pipeline had already
flagged as silent, result-changing, and high severity. The gap was never selection.
A record demands a fixture, a backend, per-quantity expectation prose, and an
exposure probe before a single number is measured — so a claim got *tested* only
after someone had committed an afternoon to *publishing* it.

A **screen** is the cheap half: one fixture, run against the release that carried
the fix and the release immediately before it, asking whether any number moved. No
prose, no expectations, no probe. Only a screen that moves something is promoted.

That also buys the thing a hand-curated base cannot report — a **denominator**.
Every finding published here so far is a success, because failures were never cheap
enough to attempt. Of **13 claims screened**: 5 moved a number, 4 did not, 4 could
not be evaluated. `docs/screening.md` carries the table.

**Quantities are not chosen.** `cc_flatten` dumps every number the call returned,
because deciding which ten matter requires already understanding the bug — which is
exactly what a screen has not done. Two of the five confirmations adjudicate
themselves out of that dump:

- `lmtest` 0.9-35: on a rank-deficient fit, `bptest`'s **degrees of freedom go 3 →
  2** and the p-value with them, while the statistic is untouched and a
  well-conditioned fit is identical on all three. "Aliased regressors were counted"
  is visible in the numbers, not inferred from the prose.
- `psych` 1.9.12: **all twelve** `ICC` confidence bounds move; every point estimate,
  F, and degrees-of-freedom stays put. The claim is about the interval, and only the
  interval moved.
- `estimatr` 0.6.0: with weights and blocks together, 0.4.0 returned **no standard
  error and no p-value at all**. They do not differ across versions — they *appear*.

**`NOT_TRIGGERED` is not a refutation.** It says a particular fixture did not move a
number, which is a falsifiable statement about the fixture, not a verdict on a
maintainer. That is the same distinction `ABSENT` taught the bisect, and it is
enforced rather than hoped for: every fixture declares a **positive control** saying
what it checked to know the condition was met — `nlevels(z) > 2`, `anyNA(d)`,
`anyNA(coef(fit))` — and a run without one is `UNEVALUABLE`, because "nothing moved"
and "nothing ran" are otherwise indistinguishable.

**Fixtures are per-package, not per-bug.** The 41 entries span 16 packages, so one
dataset with a superset of columns serves many claims and what varies is the call.

**Where the fix version is not a release.** `survival`'s NEWS is organised under
headings like `2.35` that CRAN never shipped, and several versions it names went out
through the author's own channel; four of the thirteen screens straddle their stated
version rather than pinning it. The report marks them, because a movement across a
span is attributable to the span.

## How far back any of this reaches

Screening is bounded by what will still compile, and that boundary is sharper than
expected. `docs/reach.md` groups every recorded failure by its cause; the largest
class is a single typedef.

**`survival` — the package with the most candidates — is the least reachable.**
Eighteen of its archived versions fail on `unknown type name 'Sint'`, an S-PLUS-era
typedef R no longer defines, so its floor is **3.4-0 (2022-08-09)** and eleven of its
twelve shortlisted claims sit below it. Others fail on `Calloc` (renamed `R_Calloc`
in R 4.2), `NAMED`, `DOUBLE_EPS`, or missing gettext headers.

Two failure classes are *not* walls and are treated differently:

- **A missing dependency is an accident of this machine.** Installing from a URL
  means `repos = NULL`, which switches off dependency resolution entirely — `psych`
  failed on all six of its versions purely for want of `mnormt`. The missing package
  is fetched and the build retried once, which recovered every one of them.
- **A dependency that no longer exists is a wall again.** `plm` 1.2-5 and 1.2-6 need
  `kinship`, removed from CRAN in 2012, and with them go three claims.

**Building is not the only wall, and it is the one that announces itself.** `psych`
1.5.8 installs cleanly and then refuses to run: its own code says `if (class(x) ==
"try-error")`, an error since R 4.2 when the condition is longer than one. A package
can be buildable and unusable, so a floor is a lower bound on reach, never a promise.

## The bug pipeline

Five stages, each leaving a durable artifact, so a session picks up where the last
one stopped instead of re-deriving the shortlist:

| stage | command | artifact | status |
|---|---|---|---|
| triage | hand-written from a changelog entry | `bug.yaml` | `CANDIDATE` |
| probe | `kasauti bug probe <id>` | `exposure.csv` | `PROBED` |
| papers | `kasauti bug papers <id>` | `papers.csv` | `LINKED` |
| verify | `kasauti run <case-id>` | results JSON | `VERIFIED` / `REFUTED` / `NOT_REPRODUCED` |
| write | hand-written | `NOTES.md` | — |

**Failed candidates stay in the tree.** `REFUTED` and `NOT_REPRODUCED` are results.
A lead that did not survive execution is exactly what a later session must not
spend an afternoon rediscovering.

## Exposure is always a pair

`scripts_calling_function` and `scripts_meeting_probe`, never one alone, with the
probe regex stored in the record so a reader can judge the bound rather than trust
it. This is not fussiness — it is the single most consequential thing the pipeline
does:

- `sandwich` 2.5-0 looked like **76 scripts**. The bug needs `lm()` with a matrix
  response. **One** corpus script combines the two.
- `sandwich` 3.0-2 looked like **37**. `vcovCL` defaults to HC1, never HC2, so the
  caller must have asked for it: **6**.

A regex over source text shows a script *could* have met the triggering condition,
never that it did. Both numbers are upper bounds; the narrowed one is just tighter.

Two further corrections the corpus forced:

**Vendored dependencies produce false positives.** One QJE archive bundles an entire
site-packages — 3,839 Python files including scikit-learn's own test suite. Left
unfiltered, `test_supervised.py` counts as a paper exercising the buggy function,
which is exactly backwards: that is the library testing itself.

**Zero papers in window is often underpowered, not negative.** Of 12,048 dated
archives, 63% predate a 2022 fix and 28% predate a 2018 one. At a narrowed exposure
of one to six archives, zero is what chance produces. The consequence is a selection
rule: chase bugs whose triggering conditions are *common*.

**And sometimes zero is simply true.** `lfe` is the mirror image: 244 scripts call
`felm`, 22 use two-way clustering, and those resolve to 12 archives — of which
**none** predates the 2016 fix. The correction is old and the corpus is recent, so
every affected analysis ran against a version that already had it. The finding
stands on its own terms; in this corpus it corrupted nothing. Reporting the 244
alone would have overstated the consequence by orders of magnitude, which is what
the funnel exists to prevent.

**A plausible narrowing is worth nothing until its matches are read.** The `lfe`
probe took four attempts, each of which looked correct: `[^;]` admitted newlines and
borrowed pipes from a later call (58 matches); anchoring to newlines lost the 115
scripts with multi-line `felm` calls (14); a lookahead fixed both but landed on the
instrument field of IV specifications (26); excluding `~` from the cluster field,
which never contains one, gave the right answer (**22**).

## The result contract

Backends are separate processes exchanging JSON. No `rpy2` — the subprocess contract
keeps languages at arm's length and makes a pinned old package version just another
backend.

```json
{
  "case_id": "hac_newey_west",
  "backend": "r",
  "env": {"language": "R", "version": "4.6.0", "packages": {"sandwich": "3.1-2"}},
  "status": "ok",
  "quantities": {"se.x@newey_west": 3.3676734944},
  "diagnostics": {"converged": true}
}
```

`status: "error"` is a *result*, not a harness failure — statsmodels refusing to fit
a separated logit belongs in the table beside the packages that did fit it.

Relative difference maps to `AGREE` (< 1e-8), `NUMERIC` (< 1e-5), or `DIVERGE`, with
a noise floor: two values both below 1e-12 are equal, because comparing a denormal
against an exact zero otherwise reports a large relative difference for two numbers
that are zero for every purpose.

Each case then declares the verdict it *expects*, with a reason required whenever
that is not agreement. This makes the suite a regression test rather than a snapshot:
it fires when reality changes — an upgrade closes a gap, or opens one — not merely
when reality is surprising.

## Determinism

One generator per case writes `data.csv`; every backend reads the same bytes, and the
report carries its SHA-256. That rules out "the two languages saw different data" as
an explanation for any divergence. Reports contain no timestamps, so two runs of an
unchanged suite are byte-identical and `git diff` on the report is exactly the set of
things that changed about the world.

## Usage

```bash
make install
kasauti list                     # every verified bug, as a runnable case
kasauti run --all --strict       # non-zero exit on any undocumented divergence
kasauti bug status               # the record's pipeline state
kasauti bug index                # validate records, regenerate all four views
kasauti bug probe <bug-id>       # narrow exposure by the conditions probe
kasauti bug papers <bug-id>      # resolve scripts to DOIs, dates, journals
kasauti bug rank                 # order candidates by estimated paper reach
kasauti screen queue             # every declared claim, and whether it has run
kasauti screen run               # test claims against the release before the fix
kasauti screen report            # what moved, what did not, what could not be told
kasauti frame packages           # select packages: task views ∩ corpus usage
kasauti frame extract            # recover call sites from the corpus
kasauti frame loads              # record which packages each script loads
kasauti frame harvest            # fetch changelogs, releases, exports
kasauti frame build              # rank the procedures the corpus calls
kasauti classify report          # judged-vs-unjudged coverage, yield by package
kasauti build audit              # how far back each package still installs
kasauti frame usage              # corpus, reverse dependencies, downloads
kasauti sweep <package>          # run every probe against every release
kasauti episodes                 # durations, with their censoring
kasauti manifest                 # hash every released table
make data                        # rebuild every derived table
make analysis                    # the estimands, in R
make check                       # lint, types, tests
```

Some cases need a pinned old package. They are marked `optional`, so the suite runs
without them and reports the backend as skipped. A pinned backend names its library
as `${KASAUTI_RLIBS}/<package>_<version>` rather than a literal path — the variable
defaults to `~/.cache/kasauti/rlibs` and can point anywhere:

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/sandwich/sandwich_2.4-0.tar.gz",
  repos = NULL, type = "source", lib = "~/.cache/kasauti/rlibs/sandwich_2.4-0")'
```

**Every build is recorded, successes and failures alike.** `data/builds.csv` holds
one row per `(package, version)` with the R version it was tried against, so a
version that will not compile costs its timeout once rather than once per bisect,
screen, and sweep. That ledger is also a measurement: `kasauti build audit` reads
the **buildability floor** off it — the oldest release of each package that still
installs against a current toolchain, which is the hard limit on how far back any
of this can reach. `fixest` stops at 0.9.0 (2021-06-19), where its templated C++
begins to fail; `sandwich` reaches 2.2-1 (2009-02-05), just past R making
`NAMESPACE` mandatory.

Python needs no side library — `uv` builds each environment on demand — but it does
need the whole ABI-coupled stack pinned, which bounds how far back Python archaeology
can reach. Running a 2021 scikit-learn takes `--python 3.10` (no newer wheel exists),
`numpy<2` (the wheel is built against the numpy 1.x C ABI), and `--no-project`. R
source packages build against any recent R and have no equivalent ceiling.

## Limits

Agreement is not correctness, and disagreement is usually not a bug. Most divergence
traces to differing defaults, or to similarly-named options meaning different things —
`cadjust=FALSE` and `use_correction=False` are not the same switch. The deliverable is
a classified catalogue, and "both right, conventions differ" is both the largest class
and the most useful to practitioners.

Changelogs are self-reported. `survival` documents 114 versions meticulously; `MASS`
has no version structure at all. **27 of the 131 selected packages ship no
machine-readable changelog whatsoever** — `arm`, `MCMCpack`, `lavaan`, `rdrobust`,
`grf` among them. They contribute zero candidates, and that is a fact about their
release notes, not about their correctness. Raw bug counts across packages measure
candor at least as much as bugginess, so NEWS thoroughness travels with every count.

**The classification tail is unread, not cleared.** Every entry is judged by hand, so
the queue is finite: **207 of 369** exposed entries are read, worked in descending
exposure, and nothing in the unjudged 162 touches more than 25 corpus scripts.
`kasauti classify report` states this each time it runs. A bug sitting in that tail
has not been ruled out; it has not been looked at.

**Python coverage is bounded by the corpus, not by the selection.** Of 6,233 parsed
Python scripts, the inferential imports are `numpy` (2,914), `scipy` (881), `sklearn`
(254), and `statsmodels` (46); the next econometrics library, `linearmodels`, appears
in 4. Adding Python packages would add changelog text and no exposure. R's `lm` alone
appears in 643 scripts — an order of magnitude more than all of statsmodels.

**Python exposure counts are far weaker evidence than R's, and the reason is
structural.** The funnel now applies the same export restriction R gets — module-level
names introspected from a throwaway `uv` environment, minus array plumbing and every
Python builtin — which cut exposed candidates from 587 to 271 and put real estimator
bugs at the top (`Normalizer` with `norm='max'` not taking absolute values, an
`AdaBoostClassifier` SAMME decision function, `NMF` initialization). But R's packages
export *procedures*: nothing but `sandwich` means `vcovHC`, so "76 scripts call it" is
informative. numpy exports *primitives*, and "1,182 scripts call something numpy
exports" says only that they are Python scripts. For `numpy` and `scipy` the calling
count is a technically-true upper bound carrying almost no information, which is why
the classified rate stays R-only. `kasauti classify pending --language Python` queues
the Python candidates; none are judged yet.

Publication date is a weak proxy for when an analysis was run, in both directions.
One archive here went up six weeks *after* the fix that would have affected it.
