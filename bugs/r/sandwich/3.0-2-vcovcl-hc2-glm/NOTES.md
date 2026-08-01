# sandwich 3.0-2: wide and mild, where 2.5-0 was narrow and severe

> Bug fix in `vcovCL(..., type = "HC2")` for `glm` objects or `lm` objects with
> weights. The code had erroneously assumed that the hat matrices were all
> symmetric (as in the `lm` case without weights). This is corrected now.
> — sandwich 3.0-2, 2022-06-15

Run under 3.0-1 and 3.1-2 on identical data, nine quantities. Exactly the two the
changelog names move, and the other seven are bit-identical:

| quantity | 3.0-1 (buggy) | 3.1-2 (fixed) | reldiff |
|---|---|---|---|
| **`se.x@glm_HC2`** | **3.257220214** | **3.241862121** | **4.7e-03** |
| **`se.x@weighted_HC2`** | **0.6775907611** | **0.6877735645** | **1.5e-02** |
| `se.x@glm_HC0` | 2.786367932 | 2.786367932 | 0 |
| `se.x@glm_HC3` | 4.046073276 | 4.046073276 | 0 |
| `se.x@weighted_HC0` | 0.5707255963 | 0.5707255963 | 0 |
| `se.x@weighted_HC3` | 0.8845687162 | 0.8845687162 | 0 |
| `se.x@plain_HC0` | 0.5882135563 | 0.5882135563 | 0 |
| `se.x@plain_HC2` | 0.6985358402 | 0.6985358402 | 0 |
| `se.x@plain_HC3` | 0.891727573 | 0.891727573 | 0 |

The confinement is exact. HC0 and HC3 are untouched under every fit; the
unweighted `lm` is untouched under every type. The changelog neither overstates
nor understates its own reach — which is worth recording, because the previous
entry in this record does overstate, at least as a reader would parse it.

## The contrast with `sandwich-2.5-0-vcovhc-mlm-sign`

These two bugs sit at opposite corners, and neither severity nor exposure alone
would order them correctly:

| | 2.5-0 (`vcovHC.mlm`) | 3.0-2 (`vcovCL` HC2) |
|---|---|---|
| magnitude | sign flip; one element 33x | 0.5% to 1.5% |
| triggering condition | `lm()` with a matrix response | `glm` or weighted `lm`, `type="HC2"` |
| scripts calling the function | 76 | 37 |
| scripts matching the probe | **1** | **6** |
| severity | HIGH | MEDIUM |

The narrow one is the dangerous one. A half-percent move in a standard error
rarely flips a conclusion; a sign flip in a cross-equation covariance can invert
a joint test. But the narrow one reaches almost nobody, and the mild one reaches
six times as many scripts. Ranking on either axis alone gets the wrong answer.

## Why the probe needs both halves

`vcovCL`'s `type` defaults to `HC1` (or `HC0`) and **never** to `HC2` — confirmed
by reading `meatCL`. So the caller has to ask for `HC2` explicitly, which makes
it a hard requirement rather than a common default:

- ask only for `vcovCL` → 37 scripts, most of which never reach the defect
- ask for `HC2` **and** (`glm(` or `weights=`) → **6 scripts**

The probe matches the strings anywhere in the file rather than proving they meet
at one call site, so 6 is still an over-count. It is written into `bug.yaml` so a
reader can judge that rather than take it on trust.

## Papers: zero in window, and why that is not the finding it looks like

The 6 matching scripts resolve to 3 archives, none published before the fix:

| archive | published | |
|---|---|---|
| Do Politically Irrelevant Events Cause Conflict? … Protests in Africa | 2022-07-28 | 6 weeks after |
| Drilling Deadlines and Oil and Gas Development | 2023-10-17 | |
| A Demand Curve For Disaster Recovery Loans | 2023-11-16 | |

**This is underpowered, not negative.** The corpus skews recent: of 12,048 dated
Dataverse archives, only 63.2% predate this fix and only 28.4% predate the 2018
one. With a narrowed exposure of 3 archives and a base rate near 0.6, zero
in-window is roughly what chance produces. It is not evidence that the bug
reached no published work — it is evidence that a probe-matched sample this small
cannot answer the question either way.

Two consequences worth carrying forward:

1. **Paper-level claims need wider bugs or a bigger corpus.** At a narrowed
   exposure of one to six scripts, the in-window count is noise. The interesting
   bugs for this question are the ones whose conditions are *common*.
2. **Publication date is a weak proxy, and the first row shows it.** That archive
   went up six weeks after the fix shipped. The analysis behind it was certainly
   run earlier, quite possibly against 3.0-1. Window membership by archive date
   is necessary-not-sufficient in both directions, and here it plausibly
   excludes a genuine exposure.

## Reproducing

```bash
Rscript -e 'install.packages(
  "https://cran.r-project.org/src/contrib/Archive/sandwich/sandwich_3.0-1.tar.gz",
  repos = NULL, type = "source", lib = "/tmp/rlibs/sandwich_3.0-1")'
kasauti run sandwich_vcovcl_hc2
kasauti bug probe sandwich-3.0-2-vcovcl-hc2-glm
kasauti bug papers sandwich-3.0-2-vcovcl-hc2-glm --enrich
```

## Why this one cannot be bisected

Wrong for **at least 4.9 years** -- 2.4-0 (2017-07-26) already has it -- and the
introduction was not bracketed. The reason is this record's own reproducer rather
than anything about the versions.

`run_r.R` wraps each call in `try(silent = TRUE)` and writes `NA_real_` on
failure, which is the right thing for a case that fits three models under three
covariance types and wants a full table either way. But it destroys the evidence a
bisect needs. Against a version predating `vcovCL`, the run completes cleanly with
every quantity null -- indistinguishable from a version where the function exists
and broke. Thirty-one versions were tested and every one below 2.4-0 came back
"produced no comparable quantity", so the bisect correctly refused to conclude.

The lesson generalises to how reproducers should be written when they may later be
bisected: let the error escape, or record it, because "this code did not exist
yet" and "this code was broken" are the two states the whole method turns on.
