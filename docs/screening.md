# Screening changelog claims

1 claim(s) declared across 1 package fixture(s); **1** screened.

A screen runs one fixture against the release that carried a fix and the release immediately before it, and asks whether any number moved. It is the cheap half of a bug record: no prose, no per-quantity expectations, no exposure probe. Only a screen that moved something is promoted.

## Verdicts

| verdict | n | meaning |
|---|---|---|
| `MOVED` | 1 | a quantity differs between the two releases |
| `NOT_TRIGGERED` | 0 | they agree; the fixture did not reach the defect |
| `UNEVALUABLE` | 0 | a version would not build, or the call errored |

**`NOT_TRIGGERED` is not a refutation.** It says a particular fixture, written from a particular reading of the entry, did not move a number -- which is a falsifiable statement about the fixture, not a verdict on the maintainer. Every fixture states a positive control, so a run that never reached the code is reported as `UNEVALUABLE` instead.

## What was screened

| entry | versions | verdict | moved | largest | control |
|---|---|---|---|---|---|
| `sandwich@2.5-0#7` | 2.4-0 → 2.5-0 | `MOVED` | 18/36 | 1.75e+00 | lm(cbind(y, y2) ~ .) is a multivariate lm, so vcovHC dispatches to vcovHC.mlm |

## Fixtures

One fixture per package, not per bug. The shortlist concentrates -- `survival` alone is twelve claims -- so a dataset written once serves many entries, and what varies per claim is the call and its control.

* `fixtures/sandwich/`
