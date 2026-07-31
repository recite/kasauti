# concord

Are the numbers right?

Two questions about statistical software, one comparison engine.

**Translation** — the same procedure is implemented independently in R and Python.
Run both, diff the numbers. Where they agree, that is weak evidence both are right.
Where they disagree, something is worth knowing: usually a default, occasionally a bug.

**Archaeology** — package changelogs are a confession log. Mine them for fixes that
changed results, work out when the bug was live, and trace it to the replication
archives that called the affected function during that window.

The two share a core, because archaeology's payoff step — install the buggy version
and the fixed version, run the same script under both, diff the numbers — is the
translation engine with *backend = package version* instead of *backend = language*.

## What it has found

Every number below was measured by running the thing, not predicted.

| finding | |
|---|---|
| R and Python's Newey–West standard errors differ **7×** out of the box | neither is wrong; R prewhitens and auto-selects bandwidth, statsmodels does neither |
| R's `glm` reports **p = 0.9995** where Firth reports **p = 0.0011** | separated data; the Wald statistic collapses as the standard error diverges |
| `sklearn.LogisticRegression()` silently applies L2 at `C=1.0` | its "unpenalized" coefficient is a function of `tol`, not of the data |
| GLM residual df is **30 or 3** for the same fit | statsmodels `freq_weights` vs R `glm(weights=)`; coefficients and SEs agree exactly |
| Normal equations keep **7.1** correct digits where R's QR keeps **13.0** | NIST Longley; every backend agrees to 7 digits, so comparison alone calls it unanimous |
| `sandwich` 2.5-0 flipped the sign of cross-equation covariances | verified against 2.4-0; within-equation blocks bit-identical |
| `scikit-learn` 1.0.2 returns **1.25** from a metric bounded on [0, 1] | `normalized_mutual_info_score`, `average_method` of `min` or `geometric` |

## Three oracles, because agreement is not correctness

Two packages sharing a wrong formula agree, and you learn nothing. So a case can
be judged three ways, and each catches what the others cannot:

| oracle | question | example |
|---|---|---|
| **comparison** | do independent implementations agree? | `hac_newey_west` |
| **metamorphic** | does one implementation agree with *itself* under a transformation that cannot change the answer? | `glm_weights_semantics` |
| **certified** | does it match a known-true value? | `nist_longley` |

Only the third can say who is *right*. Only the second needs no second implementation.

## Layout

```
cases/<family>/<case>/        translation: cross-implementation comparisons
bugs/<language>/<package>/<version-slug>/    archaeology: one directory per bug
lib/                         shared backend helpers, located via $CONCORD_LIB
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
discovered by the same runner as any translation case. The lifecycle falls out of
the files.

## The bug pipeline

Five stages, each leaving a durable artifact, so a session picks up where the last
one stopped instead of re-deriving the shortlist:

| stage | command | artifact | status |
|---|---|---|---|
| triage | hand-written from a changelog entry | `bug.yaml` | `CANDIDATE` |
| probe | `concord bug probe <id>` | `exposure.csv` | `PROBED` |
| papers | `concord bug papers <id>` | `papers.csv` | `LINKED` |
| verify | `concord run <case-id>` | results JSON | `VERIFIED` / `REFUTED` / `NOT_REPRODUCED` |
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
concord list                     # every case, both tracks
concord run --all --strict       # non-zero exit on any undocumented divergence
concord bug status               # the record's pipeline state
concord bug index                # validate records, regenerate all four views
concord bug probe <bug-id>       # narrow exposure by the conditions probe
concord bug papers <bug-id>      # resolve scripts to DOIs, dates, journals
make check                       # lint, types, tests
```

Some cases need a pinned old package. They are marked `optional`, so the suite runs
without them and reports the backend as skipped:

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/sandwich/sandwich_2.4-0.tar.gz",
  repos = NULL, type = "source", lib = "/tmp/rlibs/sandwich_2.4-0")'
```

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
has no version structure at all. Raw bug counts across packages measure candor at
least as much as bugginess, so NEWS thoroughness travels with every count.

Publication date is a weak proxy for when an analysis was run, in both directions.
One archive here went up six weeks *after* the fix that would have affected it.
