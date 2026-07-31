# fixest 0.10.4: `fixef()` returned fixed effects that do not reconstruct the fit

> fix major bug related to the extraction of fixed-effects (function `fixef`)
> when there are 3+ fixed-effects. This bug led to, in some specific
> circumstances, wrong values for the fixed-effects coefficients.
>
> — fixest NEWS 0.10.4, 2022-03-31

Chosen by `kasauti bug rank`, which put it top of the unverified list — the first
record selected by estimated paper reach rather than by raw exposure.

## Compare adjacent versions, or you measure everything at once

The first attempt compared 0.10.3 against current 0.14.2 and found a difference
immediately — which was the wrong difference. In that pairing 0.14.2 estimates on
70 rows where 0.10.3 uses 71, because somewhere in the four minor versions between
them fixest began **dropping singleton fixed-effect groups**. The `id` level with
exactly one observation vanishes, and every extracted effect shifts.

That is a real change and a deliberate one; it is not this bug. Re-running against
0.10.4, the immediately following release, isolated the fix: of 240 randomised
designs, **exactly one** diverged, and it was a four-fixed-effect specification —
consistent with "3+ fixed-effects".

The general lesson: an archaeology backend pinned several versions away measures
the union of everything that changed. Pin the adjacent release.

## A case that adjudicates itself

Extracted fixed effects are *defined* by what they reconstruct. The estimator
sweeps them out; `fixef()` solves for them afterwards; added back to `Xb` they must
return the fitted values. So this case needs no third implementation to say which
version is right — the buggy one contradicts the definition of the quantity it
reports.

| quantity | 0.10.3 | 0.10.4 |
|---|---|---|
| `Xb + Σ FE − fitted`, max abs | **3.366909547** | 4.579378239e-06 |
| `coef(x)` | 1.006553381002 | 1.006553381002 |
| first `id` effect | 1.278791359 | −1.458587022 |
| first `reg` effect | 0.000000000 | 3.975387020 |
| first `yr` effect | 0.000000000 | −0.872215861 |
| first `ind` effect | 0.000000000 | −0.365792980 |

Three of the four dimensions came back pinned to exactly `0` at their first level,
which is what makes this hard to notice: a column of fixed effects beginning at
zero looks like a correctly normalised one. And the regression coefficient is
identical, so a paper reporting only `x` was never affected. A paper reporting,
tabulating, or plotting the fixed effects was.

Both versions print `NOTE: The fixed-effects are not regular, they cannot be
straightforwardly interpreted.` — so a user was warned about *interpretation*, but
not that the numbers were wrong. 0.10.4 adds "The number of references is only
approximate." Applied code frequently sets `notes = FALSE`.

## The near-miss: a fourth collision class

The first probe was `fixef\s*\(|getfe\s*\(`, which matched all 28 exposed scripts,
and the paper linkage came back with **1 archive published before the fix** — the
first non-zero paper count in the whole study.

It was wrong. The archive is `10.7910/DVN/AGWJQJ`, and its `fixef(mod1)` calls sit
beside `vcov(mod1)` and significance stars — the mixed-model idiom — with `mod1`
built by **`lm()`**, not `feols()`. `fixef` is exported by **six** packages in this
frame: `brms`, `fixest`, `lme4`, `nlme`, `plm`, `rstanarm`. Of the 28 scripts
calling it, 12 load `nlme`, 6 load `lme4`, and **2** load `fixest`.

Neither existing shadow rule catches this. Base R does not export `fixef`, and none
of the six owners is a non-inferential package — this is two *computing* packages
sharing a name. The probe now requires the script to load `fixest` at all:

| | scripts | archives | in window |
|---|---|---|---|
| `fixef(` anywhere | 28 | 9 | **1** |
| plus `library(fixest)` or `fixest::` | **4** | 2 | **0** |

So the honest count is zero, and the study's apparent first affected paper was an
`lm` model calling a mixed-models function.

This generalises: **21.8% of exposed entries (84 of 386) rest on at least one name
exported by two or more frame packages** and not already handled — `coordinates`
(raster/sp, 219 scripts), `vcovHC` (plm/sandwich, 76), `Surv` (rms/rstanarm/
survival, 51), `lmer` (lme4/lmerTest, 36). Some are benign, because one package
re-exports another's function and the call really does reach the owner. Some, like
`fixef`, are not. Requiring the owning package to be loaded is the rule that
separates them, and applying it across the funnel rather than one record at a time
is the outstanding work this record documents.
