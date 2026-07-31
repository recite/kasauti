# Bug record

7 records: 6 verified, 1 refuted or not reproduced, 0 still open.

Exposure is reported as a pair. `calls` counts scripts calling an
affected function and is an upper bound; `probe` counts those also
matching the bug's conditions probe. A probe is a regular expression
over source text -- it shows a script *could* have met the triggering
condition, never that it did. Neither number means much alone.

| bug | severity | silent | calls | probe | papers | status |
|---|---|---|---|---|---|---|
| [`r/lfe/2.5-multiway-cluster-psdef`](r/lfe/2.5-multiway-cluster-psdef/) | HIGH | yes | 244 | 22 | 0* | VERIFIED |
| [`r/fixest/0.10.4-fixef-three-way`](r/fixest/0.10.4-fixef-three-way/) | HIGH | yes | 28 | 4 | 0* | VERIFIED |
| [`r/sandwich/2.5-0-vcovhc-mlm-sign`](r/sandwich/2.5-0-vcovhc-mlm-sign/) | HIGH | yes | 76 | 1 | 0* | VERIFIED |
| [`python/scikit-learn/1.1.0-nmi-unbounded`](python/scikit-learn/1.1.0-nmi-unbounded/) | HIGH | yes | 0 | 0 | 0* | VERIFIED |
| [`r/mgcv/1.9-0-multinom-variance`](r/mgcv/1.9-0-multinom-variance/) | HIGH | yes | -- | -- | -- | NOT_REPRODUCED |
| [`r/sandwich/3.0-2-vcovcl-hc2-glm`](r/sandwich/3.0-2-vcovcl-hc2-glm/) | MEDIUM | yes | 37 | 6 | 0* | VERIFIED |
| [`r/plm/1.5-13-vcovhc-white-singleton`](r/plm/1.5-13-vcovhc-white-singleton/) | LOW | no | 76 | 11 | -- | VERIFIED |

`*` marks a left-censored window: the version that introduced the
defect is not recorded, so the paper count covers everything published
before the fix rather than only the interval when the bug was live.
Those counts are upper bounds, not comparable with uncensored ones.

## Did not survive verification

Kept deliberately. A candidate that failed is the most expensive
thing this pipeline produces, and deleting it invites the same lead
being chased again.

- `r/mgcv/1.9-0-multinom-variance` -- NOT_REPRODUCED: Not reproduced. The entry is almost certainly accurate -- "a counter was initialized in the wrong place" is too specific to be invented -- but the probe did not find the configuration that triggers it. Most likely candidates not yet tried: a different link or model structure, more than two linear predictors sharing a smooth, or a quantity other than vcov() and edf. Recorded so the next session starts from here rather than re-deriving it.
