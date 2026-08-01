# Data dictionary

Six tables. `data/manifest.json` carries the SHA-256 and row count of each, so a
claim traces to the bytes it was computed from.

Rebuild everything derived with `make data`; recompute the estimands with
`make analysis`. Sweeps are deliberately not a Make target — they take hours and
are the only stage touching the network and the compiler, so they are run by hand
(`kasauti sweep <package>`) and their timelines are tracked under `sweeps/`.

## The unit of analysis

`(package, release, probe)`. Packages and probes are chosen here; releases are a
**census** within package. That is the point of the design: a changelog entry is
selected by a maintainer, and exists only if someone noticed a bug, fixed it, and
wrote it down. A release exists whether or not anyone noticed anything.

---

## `data/episodes.csv` — one row per stretch a value held

The duration table. Each row is a span over which one probe's answer did not
change, with its own censoring attached.

| column | meaning |
|---|---|
| `package`, `probe` | which package, and which probe script |
| `opened`, `opened_on` | release at which the value first held, and its date |
| `opened_after`, `opened_after_on` | last release known to hold the *previous* value; empty when the episode was already in force at the floor |
| `closed`, `closed_on` | release at which the value stopped holding; empty when still holding |
| `closed_after`, `closed_after_on` | last release known to hold *this* value |
| `start` | `OBSERVED`, `LEFT_CENSORED`, or `BORN` |
| `end` | `CLOSED` or `RIGHT_CENSORED` |
| `exact` | 1 when both bounding intervals are one release wide |
| `releases` | evaluable releases spanned |
| `lower_days` | days that **certainly** elapsed: `opened_on` → `closed_after_on` |
| `upper_days` | days that **may** have: `opened_after_on` → `closed_on`; empty when right-censored |
| `opened_documented`, `closed_documented` | 1 when the changelog over the corresponding interval names a function the probe calls |

**`lower_days` and `upper_days` are an interval, not an estimate and its error.**
Fit with `Surv(lower_days, upper_days, type = "interval2")`; a right-censored
episode carries `NA` on the right, which is the same encoding.

`start` distinguishes three different things and they must not be pooled:

* `OBSERVED` — a change point opened it. The date is measured.
* `LEFT_CENSORED` — it was already in force at the oldest release that would
  build. Its length is a lower bound. Not rare: `sandwich` reaches 2009,
  `survival` only 2022.
* `BORN` — the releases before it failed because the *code did not exist*, not
  because they would not build. That is a start date, not censoring.

## `data/changes.csv` — one row per point where a number moved

| column | meaning |
|---|---|
| `package`, `probe` | which package, and which probe script |
| `at`, `at_on` | first release observed to hold the new value |
| `after`, `after_on` | last release observed to hold the old one |
| `gaps` | releases inside that interval that could not be evaluated |
| `exact` | 1 when `gaps` is 0, so the change is pinned to one release |
| `n_moved`, `moved` | how many quantities differ, and their names (`;`-separated) |
| `max_reldiff` | largest relative difference across shared quantities |

A quantity prefixed `+` appeared and one prefixed `-` vanished: what a function
returns changing shape is a changed result.

## `data/builds.csv` — what compiled, and what refused

The coverage table, and the reason every estimate above is conditional.

| column | meaning |
|---|---|
| `package`, `version` | the archived release |
| `outcome` | `BUILT` or `FAILED` |
| `r_version`, `platform` | what it was tried against — "will not build" is a statement about a toolchain and is worthless without one |
| `detail` | the compiler's own first diagnostic, for a failure |

A version absent from this table was never asked for. Untried and failed are
different facts.

## `data/frame/packages.csv` — the sampling frame

Task views ∩ corpus usage. `package`, `usage` (corpus archives loading it), and
`views` (`;`-separated).

## `data/frame/cran_usage.csv` — usage, three ways

| column | meaning |
|---|---|
| `corpus` | social-science replication archives that load it |
| `strong` | CRAN packages declaring it in `Depends`, `Imports`, or `LinkingTo` |
| `suggests` | CRAN packages declaring it in `Suggests` |
| `downloads` | RStudio-mirror downloads, 2024-01-01 to 2024-12-31 |

**These do not measure the same thing.** Spearman correlation between corpus rank
and reverse-dependency rank is **0.32**; between the two CRAN-wide measures,
**0.88**. `lfe` is the case in point: seventh most used package in the corpus,
four reverse dependencies on all of CRAN. A frame built on ecosystem centrality
alone would never see it.

## `data/frame/sampling_frame.csv` — procedures ranked by corpus calls

What the probe batteries are drawn from, so probe selection is inherited from the
corpus rather than chosen by hand.

---

## What every estimate is conditional on

Five gates, and they all push the same way — toward shorter measured lifetimes.
Each is a column here rather than a caveat in prose.

| gate | where it is visible |
|---|---|
| **buildability** — an unbuildable release cannot be observed | `data/builds.csv`; `gaps` in `changes.csv`; `LEFT_CENSORED` in `episodes.csv` |
| **runnability** — a release can build and still refuse to run | `GAP` observations in `sweeps/*/*.json`, with the R error |
| **probe coverage** — a change no probe exercises is invisible | `probe` column; the battery is drawn from `sampling_frame.csv` |
| **documentation** — NEWS may not mention a change | `closed_documented`; this is the estimand, not an assumption |
| **eventual change** — a value still holding may be wrong and undiscovered | `RIGHT_CENSORED`; these must not be dropped |
