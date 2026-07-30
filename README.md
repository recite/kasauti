# concord

Are the numbers right?

Two questions about statistical software, attacked with one comparison engine.

**Translation.** The same procedure is implemented independently in R and in Python.
Run both, diff the numbers. Where they agree, that is weak evidence both are right.
Where they disagree, something is worth knowing — usually a default, occasionally a bug.

**Archaeology.** Package changelogs are a confession log. Mine them for fixes that
changed results, work out when the bug was live, and trace it to the replication
archives that called the affected function during that window.

The two share a core, because archaeology's payoff step — install the buggy version and
the fixed version, run the same script under both, diff the numbers — is the translation
engine with *backend = package version* substituted for *backend = language*.

## What it finds

Measured, on a deterministic 40-row dataset with no random number generation:

| | R | Python |
|---|---|---|
| OLS SE, HC1, HC3 | 0.3490954828 / 0.2756015363 / 0.2864679868 | identical to 10 digits |
| Cluster SE (G=5), defaults | 0.4264491409 | 0.4264491409 |
| Cluster SE, "no correction" | 0.3814277072 (`cadjust=FALSE`) | 0.3765058532 (`use_correction=False`) |
| Newey–West SE, defaults | 3.3676734944 | 0.4780828112 |

The last row is a factor of seven, and neither package is wrong: R's `NeweyWest`
prewhitens and selects bandwidth automatically, statsmodels does neither and requires an
explicit `maxlags`. Port an analysis between languages and the standard error moves.

Logistic regression under separation, same data, four implementations:

| | beta | what the user is told |
|---|---|---|
| `sklearn.LogisticRegression()` default | 1.441540 | nothing — L2 at `C=1.0` is applied silently |
| `sklearn`, `penalty=None` | 14.791628 | nothing |
| R `glm(family=binomial)` | 45.422578 | SE of 73292, but `converged=TRUE` |
| `statsmodels.Logit` | — | `LinAlgError: Singular matrix` |

The maximum likelihood estimate does not exist here, so no finite answer is right. The
finding is that one of these returns a plausible-looking number for a model the user did
not ask for.

## Design

Backends are separate processes exchanging JSON. No `rpy2`: the subprocess contract keeps
the languages at arm's length and makes a pinned old package version just another backend.

```
cases/<family>/<case_id>/
  case.yaml    canonical quantity names, tolerances, expected verdicts + required reasons
  data.py      deterministic generator -> data.csv (hashed into the report)
  run_r.R      -> results.r.json
  run_py.py    -> results.py.json
  NOTES.md     what differs and why
```

Every backend writes the same schema:

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

`status: "error"` is a *result*, not a harness failure — statsmodels refusing to fit a
separated logit is exactly the behavior worth recording beside the packages that did fit it.

Relative difference maps to `AGREE` (< 1e-8), `NUMERIC` (< 1e-5), or `DIVERGE`. Each case
then declares the verdict it *expects*, with a reason required whenever that is not
agreement. This makes the suite a regression test rather than a snapshot: it fires when
reality changes — an upgrade closes a gap, or opens one — not merely when reality is
surprising.

### Three oracles, not one

Agreement has a blind spot: two packages sharing a wrong formula agree, and you learn
nothing. So cases may also carry:

- **certified values** — NIST StRD and similar, where truth is known to more digits than
  any package reaches. Scores each backend independently, which is what answers *who* is
  wrong when two disagree.
- **metamorphic invariants** — relations that hold whatever the truth is. Rescaling a
  predictor must scale its coefficient exactly; frequency weights must reproduce row
  duplication. A package can fail these on its own terms.

### Determinism

One generator per case writes `data.csv`; every backend reads the same bytes, and the
report carries its SHA-256. That rules out "the two languages saw different data" as an
explanation for any divergence — otherwise the first thing a skeptical reader suspects.
Reports contain no timestamps, so two runs of an unchanged suite are byte-identical and
`git diff` on the report is exactly the set of things that changed about the world.

## Usage

```bash
make install
concord list                  # discovered cases
concord run --all             # run everything, write reports/latest.md
concord run robust_se         # one family
concord run --all --strict    # non-zero exit on any undocumented divergence
make check                    # lint, types, tests
```

## Limits

Agreement is not correctness, and disagreement is usually not a bug. Most divergence
traces to differing defaults, or to similarly-named options meaning different things
(`cadjust=FALSE` and `use_correction=False` are not the same switch). The deliverable is
a classified catalogue, and the "both right, conventions differ" class is both the
largest and the most useful to practitioners.
