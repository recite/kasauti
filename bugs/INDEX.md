# Bug record

7 records: 6 verified, 1 refuted or not reproduced, 0 still open.

Exposure is reported as a pair. `calls` counts scripts calling an
affected function and is an upper bound; `probe` counts those also
matching the bug's conditions probe. A probe is a regular expression
over source text -- it shows a script *could* have met the triggering
condition, never that it did. Neither number means much alone.

The `papers` column assumes an analysis was run on the day its archive
was published. It was not: publication trails the work by one to four
years, so that column is a **lower bound**, not a neutral estimate. The
`by lag` column shows how the count moves under one, two, and three
years of that trailing. No single lag is adopted as the answer.

| bug | severity | silent | calls | probe | papers | by lag 1/2/3 | status |
|---|---|---|---|---|---|---|---|
| [`r/lfe/2.5-multiway-cluster-psdef`](r/lfe/2.5-multiway-cluster-psdef/) | HIGH | yes | 244 | 22 | 0* | 0/0/0 | VERIFIED |
| [`r/fixest/0.10.4-fixef-three-way`](r/fixest/0.10.4-fixef-three-way/) | HIGH | yes | 4 | 4 | 0* | 0/1/2 | VERIFIED |
| [`r/sandwich/2.5-0-vcovhc-mlm-sign`](r/sandwich/2.5-0-vcovhc-mlm-sign/) | HIGH | yes | 61 | 1 | 0 | 0/0/0 | VERIFIED |
| [`python/scikit-learn/1.1.0-nmi-unbounded`](python/scikit-learn/1.1.0-nmi-unbounded/) | HIGH | yes | 0 | 0 | 0* | 0/0/0 | VERIFIED |
| [`r/mgcv/1.9-0-multinom-variance`](r/mgcv/1.9-0-multinom-variance/) | HIGH | yes | -- | -- | -- | -- | NOT_REPRODUCED |
| [`r/sandwich/3.0-2-vcovcl-hc2-glm`](r/sandwich/3.0-2-vcovcl-hc2-glm/) | MEDIUM | yes | 37 | 6 | 0* | 1/3/3 | VERIFIED |
| [`r/plm/1.5-13-vcovhc-white-singleton`](r/plm/1.5-13-vcovhc-white-singleton/) | LOW | no | 24 | 4 | -- | -- | VERIFIED |

`*` marks a left-censored window: the version that introduced the
defect is not recorded, so the paper count covers everything published
before the fix rather than only the interval when the bug was live.
Those counts are upper bounds, not comparable with uncensored ones.

## How long was it wrong

Changelogs record when a defect was fixed and almost never when it
started: of 369 exposed entries, four name an introducing version. So
these were measured by running each record's own reproducer against
archived versions until the behaviour changed.

Two columns, because a bisect answers two different questions. **Lived**
is a measured lifetime: a version without the bug was found below a
version with it. **At least** is what was observed when no such version
could be reached -- the bug was already there in the oldest release that
would still build and run, and how much older it is remains unknown.

| bug | introduced | fixed | lived | at least | evidence |
|---|---|---|---|---|---|
| [`r/sandwich/2.5-0-vcovhc-mlm-sign`](r/sandwich/2.5-0-vcovhc-mlm-sign/) | 2.2-4 (2009-12-07) | 2.5-0 (2018-08-17) | **8.7 years** | -- | run against archived versions |
| [`r/sandwich/3.0-2-vcovcl-hc2-glm`](r/sandwich/3.0-2-vcovcl-hc2-glm/) | before 2017-07-26 | 3.0-2 (2022-06-15) | -- | 4.9 years | not established |
| [`r/fixest/0.10.4-fixef-three-way`](r/fixest/0.10.4-fixef-three-way/) | before 2021-06-19 | 0.10.4 (2022-03-31) | -- | 0.8 years | not established |

4 terminal record(s) have no lifetime at all, and the
reasons are worth separating. A bisect needs a dated fix to measure
from, a reproducer that distinguishes *absent* from *broken*, and old
versions that still build. Each of those failed at least once here.


## Did not survive verification

Kept deliberately. A candidate that failed is the most expensive
thing this pipeline produces, and deleting it invites the same lead
being chased again.

- `r/mgcv/1.9-0-multinom-variance` -- NOT_REPRODUCED: Not reproduced. The entry is almost certainly accurate -- "a counter was initialized in the wrong place" is too specific to be invented -- but the probe did not find the configuration that triggers it. Most likely candidates not yet tried: a different link or model structure, more than two linear predictors sharing a smooth, or a quantity other than vcov() and edf. Recorded so the next session starts from here rather than re-deriving it.
