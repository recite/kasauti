# Classification of exposed changelog entries

163 entries from 15 R packages survive the
funnel with corpus exposure. Of those, **163** have been read and judged.

R only. The Python funnel has no export restriction, so its candidates are
noisier; mixing two different-quality samples into one rate would make the
rate meaningless.

## What the reading changed

The regular-expression layer agreed with the reading on **93**
of 163 entries and disagreed on **70** (43%).

This is the validation a hand-coded gold set was going to provide. The rules
are the baseline, the reading is the reference, and the disagreement rate is
how much the reading was worth.

| rules said | reading said | n |
|---|---|---|
| RESULT_CHANGING | RESULT_CHANGING | 93 |
| RESULT_CHANGING | DOC ** | 27 |
| RESULT_CHANGING | ERROR_TO_WORKING ** | 22 |
| RESULT_CHANGING | UNCLEAR ** | 16 |
| RESULT_CHANGING | BEHAVIOR_CHANGE ** | 4 |
| RESULT_CHANGING | FEATURE ** | 1 |

## Distribution

| category | n |
|---|---|
| RESULT_CHANGING | 93 |
| DOC | 27 |
| ERROR_TO_WORKING | 22 |
| UNCLEAR | 16 |
| BEHAVIOR_CHANGE | 4 |
| FEATURE | 1 |

Silent (quietly wrong, no error or warning): **90**; loud: 73.

**90** entries could have moved a number in a published table -- silent result-changing bugs, plus behaviour
changes, which move results whether or not anyone calls them defects.

## Shortlist: silent, result-changing, high severity

The queue the verification pass draws from. Each of these changed an
estimate, standard error, or p-value, under conditions an applied user
could plausibly hit, with nothing to signal it had happened.

| entry | functions | conditions |
|---|---|---|
| `AER@1.2-6#3` | `tobit`, `summary` | survival 2.42-7 or later installed |
| `MASS@unknown#112` | `glm.nb`, `theta.ml` | weights supplied that do not sum to n |
| `car@1.0-18#1` | `recode` | values mixing letters and numbers |
| `estimatr@0.12.0#7` | `difference_in_means` | condition1/condition2 subsetting a treatment with more than two conditions |
| `estimatr@0.6.0#11` | `difference_in_means` | both weights and blocks supplied |
| `fixest@0.10.4#0` | `fixef` | three or more sets of fixed effects |
| `fixest@0.9.0#6` | `feols` | Wald test in IV estimation with variables removed for collinearity |
| `lmtest@0.9-35#2` | `bptest` | aliased or collinear regressors |
| `mgcv@0.6-0#27` | `predict.gam` | standard errors for parametric terms |
| `mgcv@1.8-1#1` | `gam` | every gam fit in 1.8-0 -- the entry says it applied even without prior weights specified |
| `mgcv@1.8-10#1` | `bam` | discrete=TRUE with s(a,b,bs='re') terms |
| `mgcv@1.9-0#5` | `gam` | multinom family with K>=3 categories |
| `plm@1.2-6#0` | `mtest`, `pgmm` | effect='individual' with transformation='ld', and the Wald test for time dummies under effect='twoways' |
| `plm@1.2-6#1` | `pgmm` | different lags for GMM instruments |
| `plm@1.2-6#4` | `plmtest` | two-tailed tests; p-values were divided by 2 instead of multiplied |
| `plm@1.2-8#2` | `vcovBK` | matrices degenerating into vectors |
| `plm@1.5-13#0` | `vcovHC` | method='white' when any group has exactly one element |
| `plm@1.5-9#3` | `phtest` | method='aux' with NA values, or the between model (wrong degrees of freedom) |
| `quantreg@3.08#0` | `anova.rqlist` | numerator degrees of freedom were p*(m-1) instead of (p-1)*(m-1) |
| `quantreg@3.73#1` | `anova.rqlist`, `rq.test.rank` | chi-squared statistic divided by numerator df twice |
| `quantreg@4.16#5` | `boot.crq` | bootstrap weights applied twice |
| `quantreg@4.20#9` | `rq.test.rank` | denominator degrees of freedom |
| `quantreg@4.24#2` | `predict.rq` | prediction with factor covariates; xlevels were not stored on the fit |
| `quantreg@4.50#1` | `crq` | 64-bit R only; a Fortran declaration error in powell.f |
| `sandwich@2.3-1#0` | `estfun` | survreg or coxph fitted with weights, then a sandwich covariance |
| `sandwich@2.5-0#7` | `vcovHC` | multivariate lm only; off-diagonal blocks, diagonal unaffected |
| `survival@2.35#14` | `frailty`, `survfit`, `survreg` | missing values in frailty levels; case weights in SurvfitCI |
| `survival@2.35#27` | `anova.coxph` | models containing a strata term |
| `survival@2.35#8` | `Surv` | missing times and time1>=time2 both present and interleaved |
| `survival@2.37-1#15` | `coxph`, `survfit` | model with an offset, predicted curve using newdata |
| `survival@2.37-1#4` | `clogit`, `coxph` | fast subsets path; linear predictor returned in sorted rather than data order |
| `survival@2.37-3#8` | `cch` | cch models using (start, stop) survival times |
| `survival@2.38-1#16` | `residuals.coxph` | (start, stop] data with a pspline term |
| `survival@2.40-2#1` | `finegray` | finegray with a strata() term |
| `survival@2.41-2#2` | `Surv`, `survfit`, `survreg` | type='interval2' with an infinite endpoint |
| `survival@3.1-2#1` | `cox.zph` | models containing tt() terms |
| `survival@3.2-12#10` | `survreg` | large values of y, which triggered a wrong singularity decision |
| `survival@3.6-1#8` | `survfit` | case weights varying between rows in the same cluster |

