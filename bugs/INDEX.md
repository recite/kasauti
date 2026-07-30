# Bug record

2 records: 2 verified, 0 refuted or not reproduced, 0 still open.

Exposure is reported as a pair. `calls` counts scripts calling an
affected function and is an upper bound; `probe` counts those also
matching the bug's conditions probe. A probe is a regular expression
over source text -- it shows a script *could* have met the triggering
condition, never that it did. Neither number means much alone.

| bug | severity | silent | calls | probe | papers | status |
|---|---|---|---|---|---|---|
| [`sandwich-2.5-0-vcovhc-mlm-sign`](sandwich-2.5-0-vcovhc-mlm-sign/) | HIGH | yes | 76 | 1 | 0* | VERIFIED |
| [`sandwich-3.0-2-vcovcl-hc2-glm`](sandwich-3.0-2-vcovcl-hc2-glm/) | MEDIUM | yes | 37 | 6 | 0* | VERIFIED |

`*` marks a left-censored window: the version that introduced the
defect is not recorded, so the paper count covers everything published
before the fix rather than only the interval when the bug was live.
Those counts are upper bounds, not comparable with uncensored ones.
