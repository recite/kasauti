# Method

Everything the README states in one line, argued here. Most of it was learned by
getting a number wrong first, so the wrong number is kept beside the right one —
a correction with its cause removed is just an assertion.

---

## The distinction that kept collapsing

One pattern accounts for nearly every error in this project's history, and it is
the most transferable thing in it. **Two different things share one label, and
the resulting number looks completely fine.**

| collapsed | what it cost | the fix |
|---|---|---|
| "not buggy" vs *the code does not exist yet* | a bisect tested 19 versions and gave up unbracketed | `ABSENT`, which bounds the search like a working version — the same bisect then took 5 probes |
| "no bug here" vs *the fixture never reached it* | a screen would have reported a maintainer's claim as refuted | `NOT_TRIGGERED`, plus a **positive control** in every fixture |
| censored vs *born* | a measured start date thrown away, censoring rate inflated | `BORN`, when the prior releases failed because the code was unwritten |
| build failure vs *no change* | stability manufactured out of a compiler error | a `GAP` is not a data point; compare to the last **observed** release |
| moved vs *appeared* | `max_reldiff = 0` reading as noise when a function began returning a standard error | `shape_only`, summarised apart |
| "dependency unavailable" vs *dependency will not build* | sixteen `plm` releases filed under the wrong wall | the supply returns the dependency's own failure |

Each fix looks like pedantry and each one changed an answer.

---

## Which packages, and why not the ones I remembered

The frame covers **131 R packages**, chosen by intersecting two sources, neither
of them my judgment: the packages CRAN's expert-maintained [Task
Views](https://cran.r-project.org/web/views/) list for a field, and the packages
replication archives in the corpus actually load. A package qualifies by being
both recognized by the field and used in the literature — 28 relevant views list
3,509 packages, of which 131 appear in at least 10 corpus archives.

The first version of this frame named 15 packages from memory. Measuring the
corpus afterwards showed what that costs. `lfe` — Simen Gaure's fixed-effects
estimator, loaded by **222 archives** — had simply been forgotten, and its
changelog turned out to hold the single most-exposed candidate in the study: a
change to how multiway clustered standard errors handle negative eigenvalues,
touching 245 scripts. A package left off a hand-written list is
indistinguishable from a package with nothing wrong.

Judgment survives in two exclusion rules, both stated at the level of a category
rather than a package, and both falsifiable in a way an inclusion list is not:

- **`INFERENTIAL_VIEWS`** — which of CRAN's 49 views describe inference rather
  than software infrastructure, presentation, or a distant laboratory domain.
- **`NON_INFERENTIAL`** — packages whose whole job is plotting, formatting, or
  data manipulation. Unavoidable, because `ggplot2` is genuinely part of the
  Spatial and NetworkAnalysis toolkits, so no choice of views excludes it.

Cast wide at the package level, filter narrow at the function level. `broom` is
the proof: it is mostly extraction, `tidy` and `glance` are already excluded as
non-computing, and so it contributes almost nothing — without anyone having to
decide that it should.

**Exports come from the tarball, not from an install.** Attribution used to ask a
running R session `getNamespaceExports(pkg)`, which meant a package had to build
on this machine to be studied — and that build ceiling, not any principle, was
what capped the study at 15 packages. The `NAMESPACE` file sits inside the source
tarball already being downloaded for `NEWS`, so both come out of one read.
Checked against the installed namespaces it replaces, the parse loses **2 names
across 28 packages**, both traceable to a version difference rather than to the
parser.

### A name someone else owns counts only when qualified

Two rounds of this, both found by checking a suspiciously large number rather
than by reasoning:

- `Matrix` exports `diag`, `head`, `crossprod`, and `rowMeans`. Counting every
  bare `diag()` put `Matrix` at the top of the queue on **3,562 scripts** that
  meant base R's, burying `lfe` at 245.
- `alpha` is Cronbach's alpha in `psych` and colour transparency in `scales`. In
  this corpus it is written `scales::alpha` **eight** times against
  `psych::alpha` **six** — so seven `psych` entries reached the shortlist at 43
  scripts on the strength of ggplot2 code. Corrected, they sit at 6.

So the shadow set is base R **plus the non-inferential packages**, computed from
their NAMESPACEs rather than listed. Nothing is lost by shadowing the second
group: they are precisely the packages already excluded for not computing
anything, so a name they own has no business being credited to a package that
does. `car`'s `recode` entry, which is `dplyr`'s `recode` in the corpus, fell
from 46 to 2 the same way.

One collision this does not catch, recorded because it is still live: `psych`'s
ICC entry reads "confidence intervals were incorrectly based upon alpha/2", and
the `alpha` there is a significance level, not `psych::alpha`. `ICC` itself is
called by **zero** corpus scripts, so that entry's real exposure is nil. Matching
identifiers cannot tell a function name from a statistical symbol spelled the
same way.

---

## Which functions get probed

A sweep only sees changes in code it exercises, so the battery *is* the coverage
statement. Choosing those functions by hand would put back the judgment the frame
was rebuilt to remove — so a package's battery is its **most-called exported
functions in the corpus**, read off `sampling_frame.csv`, with the same filters:

- **Base R's names are base R's.** `Matrix` exports `length`, `names`, `rep`, and
  `is.na`; the frame credits it with 3,268 scripts calling `length`. Unfiltered,
  its battery would be four base-R primitives and nothing else.
- **Non-computing names are not procedures.** Extraction and formatting cannot
  move an estimate.
- **A contested name is apportioned.** This took two passes. `vcovHC` is exported
  by `sandwich` *and* `plm`, and the frame credits its 76 scripts to each — so
  `plm`'s battery led with a function whose corpus reach is mostly somebody
  else's. Dropping contested names instead cost `lme4` its `lmer`, the one
  function anyone sweeps `lme4` for, because `lmerTest` re-exports the name.
  Splitting the count in proportion to owners' corpus usage fixes both
  directions: `plm` gets 23 of `vcovHC` and falls below its own `plm()`; `lme4`
  keeps `lmer`. The split conserves the total, asserted by test.

  It is an **apportionment, not an attribution** — which package a bare call
  meant is not knowable from the call site — so every contested name is written
  out flagged, and every candidate the battery passed over is written beside the
  ones it chose. A coverage claim whose alternatives are invisible cannot be
  argued with.

One deliberate departure. `Hmisc`'s three most-called functions are an imputation
routine, a wrapper that fits over the imputations, and a reshaping helper; none
produces an estimate. Probing `upData` would have measured a reshaper's stability
and called it a bug rate. So the battery drops to the weighted-estimator family,
and the 16% coverage stays reported rather than improved by changing what it
counts.

---

## How long was it wrong: the bisect

A bug's lifetime cannot be read off the corpus. Of 369 exposed changelog entries,
**four** name the version that introduced the defect and eleven call themselves
regressions. The only way to get a real date is to run the code.

`kasauti bug bisect` drives a verified record's own reproducer against archived
CRAN versions and asks which of its two recorded outputs the run matches. No new
oracle is needed: `results.buggy.json` and `results.fixed.json` were written when
the bug was verified.

**Four outcomes per probe, not two.** `ABSENT` — the code does not exist in this
version — is the one that matters: a bug in a method nobody has written is not a
bug, and it bounds the search from below exactly as a working version would.
Before that distinction existed, the same bisect tested 19 versions and gave up;
with it, five probes settle the question. `UNEVALUABLE` stays separate from both,
because the old end of a version range is where things stop building and
collapsing "cannot tell" into "not buggy" would date every introduction to the
last version that happened to compile.

Three of four bisects did not bracket, each stopped by a different wall:

| record | result | what stopped it |
|---|---|---|
| `sandwich` 2.5-0 | **8.7 years**, bracketed | — |
| `sandwich` 3.0-2 | at least 4.9 years | its reproducer wraps calls in `try(silent = TRUE)`, so "not implemented" and "broken" look identical |
| `fixest` 0.10.4 | at least 0.8 years | templated C++ before mid-2021 will not compile against a current toolchain |
| `plm` 1.5-13 | nothing | the changelog does not date 1.5-13 |

An unbracketed bisect still yields a floor, and the floor is reported — but it is
deliberately *not* written into `introduced_on`. Closing the window at a date the
bug may predate would narrow it, and a window that is too narrow hides papers
rather than over-counting them.

---

## Screening: testing a claim without committing to publishing it

Seven records stood against a shortlist of 41 entries the pipeline had already
flagged as silent, result-changing, and high severity. The gap was never
selection. A record demands a fixture, a backend, per-quantity expectation prose,
and an exposure probe before a single number is measured — so a claim got
*tested* only after someone had committed an afternoon to *publishing* it.

A **screen** is the cheap half: one fixture, run against the release that carried
the fix and the release immediately before it, asking whether any number moved.

**Quantities are not chosen.** `cc_flatten` dumps every number the call returned,
because deciding which ten matter requires already understanding the bug. Two
confirmations adjudicate themselves out of that dump:

- `lmtest` 0.9-35: on a rank-deficient fit, `bptest`'s **degrees of freedom go
  3 → 2** and the p-value with them, while the statistic is untouched and a
  well-conditioned fit is identical on all three.
- `psych` 1.9.12: **all twelve** `ICC` confidence bounds move; every point
  estimate, F, and degrees-of-freedom stays put.

**`NOT_TRIGGERED` is not a refutation.** It says a particular fixture did not
move a number, which is a falsifiable statement about the fixture, not a verdict
on a maintainer. Every fixture declares a **positive control** — `nlevels(z) > 2`,
`anyNA(d)`, `anyNA(coef(fit))` — and a run without one is `UNEVALUABLE`, because
"nothing moved" and "nothing ran" are otherwise indistinguishable.

**Where the fix version is not a release.** `survival`'s NEWS is organised under
headings like `2.35` that CRAN never shipped, and several versions it names went
out through the author's own channel; four of the thirteen screens straddle their
stated version rather than pinning it. The report marks them, because a movement
across a span is attributable to the span.

---

## Exposure is always a pair

`scripts_calling_function` and `scripts_meeting_probe`, never one alone, with the
probe regex stored in the record so a reader can judge the bound rather than
trust it. This is not fussiness — it is the single most consequential thing the
bug pipeline does:

- `sandwich` 2.5-0 looked like **76 scripts**. The bug needs `lm()` with a matrix
  response. **One** corpus script combines the two.
- `sandwich` 3.0-2 looked like **37**. `vcovCL` defaults to HC1, never HC2, so
  the caller must have asked for it: **6**.

A regex over source text shows a script *could* have met the triggering
condition, never that it did. Both numbers are upper bounds; the narrowed one is
just tighter.

Three further corrections the corpus forced:

**Vendored dependencies produce false positives.** One QJE archive bundles an
entire site-packages — 3,839 Python files including scikit-learn's own test
suite. Left unfiltered, `test_supervised.py` counts as a paper exercising the
buggy function, which is exactly backwards: that is the library testing itself.

**Zero papers in window is often underpowered, not negative.** Of 12,048 dated
archives, 63% predate a 2022 fix and 28% predate a 2018 one. At a narrowed
exposure of one to six archives, zero is what chance produces. The consequence is
a selection rule: chase bugs whose triggering conditions are *common*.

**And sometimes zero is simply true.** `lfe` is the mirror image: 244 scripts
call `felm`, 22 use two-way clustering, and those resolve to 12 archives — of
which **none** predates the 2016 fix. The correction is old and the corpus is
recent, so every affected analysis ran against a version that already had it.
Reporting the 244 alone would have overstated the consequence by orders of
magnitude, which is what the funnel exists to prevent.

**A plausible narrowing is worth nothing until its matches are read.** The `lfe`
probe took four attempts, each of which looked correct: `[^;]` admitted newlines
and borrowed pipes from a later call (58 matches); anchoring to newlines lost the
115 scripts with multi-line `felm` calls (14); a lookahead fixed both but landed
on the instrument field of IV specifications (26); excluding `~` from the cluster
field, which never contains one, gave the right answer (**22**).

---

## The bug pipeline

Five stages, each leaving a durable artifact, so a session picks up where the
last one stopped instead of re-deriving the shortlist:

| stage | command | artifact | status |
|---|---|---|---|
| triage | hand-written from a changelog entry | `bug.yaml` | `CANDIDATE` |
| probe | `kasauti bug probe <id>` | `exposure.csv` | `PROBED` |
| papers | `kasauti bug papers <id>` | `papers.csv` | `LINKED` |
| verify | `kasauti run <case-id>` | results JSON | `VERIFIED` / `REFUTED` / `NOT_REPRODUCED` |
| write | hand-written | `NOTES.md` | — |

**Failed candidates stay in the tree.** `REFUTED` and `NOT_REPRODUCED` are
results. A lead that did not survive execution is exactly what a later session
must not spend an afternoon rediscovering.

---

## The result contract

Backends are separate processes exchanging JSON. No `rpy2` — the subprocess
contract keeps languages at arm's length and makes a pinned old package version
just another backend.

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

`status: "error"` is a *result*, not a harness failure — statsmodels refusing to
fit a separated logit belongs in the table beside the packages that did fit it.

Relative difference maps to `AGREE` (< 1e-8), `NUMERIC` (< 1e-5), or `DIVERGE`,
with a noise floor: two values both below 1e-12 are equal, because comparing a
denormal against an exact zero otherwise reports a large relative difference for
two numbers that are zero for every purpose.

Each case then declares the verdict it *expects*, with a reason required whenever
that is not agreement. This makes the suite a regression test rather than a
snapshot: it fires when reality changes — an upgrade closes a gap, or opens one —
not merely when reality is surprising.

**Determinism.** One generator per case writes `data.csv`; every backend reads
the same bytes, and the report carries its SHA-256. That rules out "the two
languages saw different data" as an explanation for any divergence. Reports
contain no timestamps, so two runs of an unchanged suite are byte-identical and
`git diff` on the report is exactly the set of things that changed about the
world.

The one probe that draws from the RNG, `MASS::mvrnorm`, pins the generator *kind*
as well as the seed. R's default generator has changed before, and a sweep that
let it float would attribute R's history to MASS.

---

## Pinned versions and the build ledger

A pinned backend names its library as `${KASAUTI_RLIBS}/<package>_<version>`
rather than a literal path — the variable defaults to `~/.cache/kasauti/rlibs`
and can point anywhere:

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/sandwich/sandwich_2.4-0.tar.gz",
  repos = NULL, type = "source", lib = "~/.cache/kasauti/rlibs/sandwich_2.4-0")'
```

**Every build is recorded, successes and failures alike.** `data/builds.csv` holds
one row per `(package, version)` with the R version it was tried against, so a
version that will not compile costs its timeout once rather than once per bisect,
screen, and sweep.

Two failure classes are *not* walls, and both get one automatic retry:

- **A missing dependency is an accident of this machine.** Installing from a URL
  means `repos = NULL`, which switches off dependency resolution entirely —
  `psych` failed on all six of its versions purely for want of `mnormt`. Fetching
  it and retrying recovered every one.
- **A missing header is too.** `mgcv` fails on `'libintl.h' file not found` on a
  machine that *has* `libintl.h`, in a package-manager prefix R was never told
  about. Environment `CPPFLAGS` cannot fix it — R's own `Makeconf` sets that
  variable and wins — so the retry writes a user `Makevars` and points
  `R_MAKEVARS_USER` at it. It did not rescue `mgcv`; it revealed the real walls
  underneath, which is the point.

A dependency CRAN **deleted** is chased into the archive, three links deep,
because a deleted package's own dependencies are often deleted too (`Rcgmin` →
`optextras`). That recovered no releases and diagnosed all of them: `kinship`,
which sixteen `plm` releases need, is not merely absent — it needs `S.h`, the
S-PLUS compatibility header R deleted. Those releases are blocked by a compiler,
not by a missing file.

**Building is not the only wall, and it is the one that announces itself.**
`psych` 1.5.8 installs cleanly and then refuses to run: its own code says
`if (class(x) == "try-error")`, an error since R 4.2 when the condition is longer
than one. A package can be buildable and unusable, so a floor is a lower bound on
reach, never a promise.

Python needs no side library — `uv` builds each environment on demand — but it
does need the whole ABI-coupled stack pinned. Running a 2021 scikit-learn takes
`--python 3.10` (no newer wheel exists), `numpy<2` (the wheel is built against
the numpy 1.x C ABI), and `--no-project`.
