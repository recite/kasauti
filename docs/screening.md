# Screening changelog claims

13 claim(s) declared across 5 package fixture(s); **13** screened.

A screen runs one fixture against the release that carried a fix and the release immediately before it, and asks whether any number moved. It is the cheap half of a bug record: no prose, no per-quantity expectations, no exposure probe. Only a screen that moved something is promoted.

## Verdicts

| verdict | n | meaning |
|---|---|---|
| `MOVED` | 5 | a quantity differs between the two releases |
| `NOT_TRIGGERED` | 4 | they agree; the fixture did not reach the defect |
| `UNEVALUABLE` | 4 | a version would not build, or the call errored |

**`NOT_TRIGGERED` is not a refutation.** It says a particular fixture, written from a particular reading of the entry, did not move a number -- which is a falsifiable statement about the fixture, not a verdict on the maintainer. Every fixture states a positive control, so a run that never reached the code is reported as `UNEVALUABLE` instead.

## What was screened

| entry | versions | verdict | moved | largest | control |
|---|---|---|---|---|---|
| `estimatr@0.6.0#11` | 0.4.0 → 0.6.0 | `MOVED` | 3/5 | 1.24e-05 | difference_in_means() had 4 blocks and unequal weights at once |
| `lmtest@0.9-35#2` | 0.9-34 → 0.9-35 | `MOVED` | 2/6 | 3.33e-01 | lm() aliased 1 coefficient(s), so bptest() saw a rank-deficient fit |
| `plm@1.5-9#3` | 1.4-0 → 1.5-12 ~ | `MOVED` | 2/6 | 4.65e-02 | phtest() ran against a between fit and via method = 'aux', both reporting degrees of freedom |
| `psych@1.9.12#26` | 1.8.12 → 1.9.12 | `MOVED` | 12/42 | 3.35e-02 | ICC() returned confidence limits alongside its estimates |
| `sandwich@2.5-0#7` | 2.4-0 → 2.5-0 | `MOVED` | 18/36 | 1.75e+00 | lm(cbind(y, y2) ~ .) is a multivariate lm, so vcovHC dispatches to vcovHC.mlm |
| `estimatr@0.12.0#7` | 0.12 → 0.14 ~ | `NOT_TRIGGERED` | 0/7 | -- | the treatment has 3 conditions, so condition1/condition2 genuinely subset it |
| `plm@1.2-8#2` | 1.2-7 → 1.2-8 | `NOT_TRIGGERED` | 0/13 | -- | vcovBK() on a one-regressor fit, where R drops the dimension, beside a two-regressor fit |
| `psych@2.4.4#3` | 2.4.3 → 2.4.6.26 ~ | `NOT_TRIGGERED` | 0/9 | -- | alpha() ran on data with 21 missing cell(s) |
| `psych@2.4.4#42` | 2.4.3 → 2.4.6.26 ~ | `NOT_TRIGGERED` | 0/6 | -- | alpha() was given a covariance matrix, not a correlation matrix |
| `plm@1.2-6#0` | 1.2-5 → 1.2-6 | `UNEVALUABLE` | -- | -- | -- |
| `plm@1.2-6#1` | 1.2-5 → 1.2-6 | `UNEVALUABLE` | -- | -- | -- |
| `plm@1.2-6#4` | 1.2-5 → 1.2-6 | `UNEVALUABLE` | -- | -- | -- |
| `psych@1.6.4#22` | 1.5.8 → 1.6.4 | `UNEVALUABLE` | -- | -- | -- |

`~` marks the 4 claim(s) whose stated fix version CRAN never shipped, so the pair straddles it rather than pinning it. `survival`'s NEWS is organised under headings like `2.35` that are not releases, and several versions it names went out through the author's own channel. A movement there is attributable to the span, not to one release, and the bisect is what narrows it.

## Fixtures

One fixture per package, not per bug. The shortlist concentrates -- `survival` alone is twelve claims -- so a dataset written once serves many entries, and what varies per claim is the call and its control.

* `fixtures/estimatr/`
* `fixtures/lmtest/`
* `fixtures/plm/`
* `fixtures/psych/`
* `fixtures/sandwich/`
