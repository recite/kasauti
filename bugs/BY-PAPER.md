# Bug record, inverted by replication archive

3 archive(s) contain a script matching some bug's conditions
probe; 0 were published while a matching bug was live.

Membership of a window is necessary, not sufficient. The archive also had
to hit the triggering condition at runtime, which no static check can
establish -- and an archive published shortly after a fix was very likely
*analysed* before it, so the window errs in both directions.

| archive | published | journal | bugs | in window |
|---|---|---|---|---|
| [dataverse/HWVUER](https://doi.org/10.7910/DVN/HWVUER) Do Politically Irrelevant Events Cause Conflict? The Cross-continental | 2022-07-28 | IOJ | `r/sandwich/3.0-2-vcovcl-hc2-glm` | 0 |
| [zenodo/10012820](https://doi.org/10.5281/zenodo.10012820) Drilling Deadlines and Oil and Gas Development | 2023-10-17 |  | `r/sandwich/2.5-0-vcovhc-mlm-sign`, `r/sandwich/3.0-2-vcovcl-hc2-glm` | 0 |
| [zenodo/10145562](https://doi.org/10.5281/zenodo.10145562) Replication Package for "A Demand Curve For Disaster Recovery Loans | 2023-11-16 |  | `r/sandwich/3.0-2-vcovcl-hc2-glm` | 0 |
