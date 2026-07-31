# Classification of exposed changelog entries

386 entries from 131 R packages survive the
funnel with corpus exposure. Of those, **211** have been read and judged.

R only. The Python funnel has no export restriction, so its candidates are
noisier; mixing two different-quality samples into one rate would make the
rate meaningless.

## Coverage

Entries are queued in descending corpus exposure, so the 211 judged
are the most-exposed ones. What is left unread is the tail:

* judged: **211** of 386 (55%)
* unjudged: **175**, none exposed to more than **25** corpus scripts

Every finding below is drawn from the judged set only. A bug sitting in
the unjudged tail has not been ruled out; it has not been looked at.

## What the reading changed

The regular-expression layer agreed with the reading on **112**
of 211 entries and disagreed on **99** (47%).

This is the validation a hand-coded gold set was going to provide. The rules
are the baseline, the reading is the reference, and the disagreement rate is
how much the reading was worth.

| rules said | reading said | n |
|---|---|---|
| RESULT_CHANGING | RESULT_CHANGING | 112 |
| RESULT_CHANGING | ERROR_TO_WORKING ** | 31 |
| RESULT_CHANGING | DOC ** | 31 |
| RESULT_CHANGING | UNCLEAR ** | 29 |
| RESULT_CHANGING | BEHAVIOR_CHANGE ** | 7 |
| RESULT_CHANGING | FEATURE ** | 1 |

## Distribution

| category | n |
|---|---|
| RESULT_CHANGING | 112 |
| ERROR_TO_WORKING | 31 |
| DOC | 31 |
| UNCLEAR | 29 |
| BEHAVIOR_CHANGE | 7 |
| FEATURE | 1 |

Silent (quietly wrong, no error or warning): **111**; loud: 100.

**112** entries could have moved a number in a published table -- silent result-changing bugs, plus behaviour
changes, which move results whether or not anyone calls them defects.

## Shortlist: silent, result-changing, high severity

The queue the verification pass draws from. Each of these changed an
estimate, standard error, or p-value, under conditions an applied user
could plausibly hit, with nothing to signal it had happened.

| entry | functions | conditions |
|---|---|---|
| `AER@1.2-6#3` | `tobit`, `summary` | survival 2.42-7 or later installed |
| `MASS@unknown#112` | `glm.nb`, `theta.ml` | weights supplied that do not sum to n |
| `MatchIt@4.4.0#7` | `matchit` | matchit(method='nearest') with ratio > 1 and reuse.max specified; a control could be matched repeatedly to the same treated unit, so the requested ratio was not delivered and every downstream estimate used the wrong matched set |
| `car@1.0-18#1` | `recode` | values mixing letters and numbers |
| `estimatr@0.12.0#7` | `difference_in_means` | condition1/condition2 subsetting a treatment with more than two conditions |
| `estimatr@0.6.0#11` | `difference_in_means` | both weights and blocks supplied |
| `fixest@0.10.4#0` | `fixef` | three or more sets of fixed effects |
| `fixest@0.9.0#6` | `feols` | Wald test in IV estimation with variables removed for collinearity |
| `lfe@2.5#3` | `btrap`, `getfe` | bootstrapped standard errors for fixed effects via getfe()/btrap() |
| `lmtest@0.9-35#2` | `bptest` | aliased or collinear regressors |
| `mgcv@0.6-0#27` | `predict.gam` | standard errors for parametric terms |
| `mgcv@1.8-1#1` | `gam` | every gam fit in 1.8-0 -- the entry says it applied even without prior weights specified |
| `mgcv@1.8-10#1` | `bam` | discrete=TRUE with s(a,b,bs='re') terms |
| `mgcv@1.9-0#5` | `gam` | multinom family with K>=3 categories |
| `mice@3.17.0#22` | `complete` | complete() on an mids object built by rbind() where the first block was imputed and the second was not; imputed values were copied into cells that should have stayed observed |
| `plm@1.2-6#0` | `mtest`, `pgmm` | effect='individual' with transformation='ld', and the Wald test for time dummies under effect='twoways' |
| `plm@1.2-6#1` | `pgmm` | different lags for GMM instruments |
| `plm@1.2-6#4` | `plmtest` | two-tailed tests; p-values were divided by 2 instead of multiplied |
| `plm@1.2-8#2` | `vcovBK` | matrices degenerating into vectors |
| `plm@1.5-9#3` | `phtest` | method='aux' with NA values, or the between model (wrong degrees of freedom) |
| `psych@1.6.4#22` | `alpha` | any alpha() call reporting a standard error |
| `psych@1.9.12#26` | `ICC` | any ICC() call reporting confidence intervals; the interval was built at alpha/2 rather than alpha, so coverage was wrong |
| `psych@2.4.4#3` | `alpha` | alpha() on data with missing values, where average R was formed from the covariance rather than the correlation |
| `psych@2.4.4#42` | `alpha` | alpha() deriving the correlation matrix indirectly through cov2cor |
| `randomForest@4.5-33#0` | `randomForest` | randomForest() with importance=TRUE and proximity=TRUE together; the proximity matrix was wrong, and only in that combination |
| `sandwich@2.3-1#0` | `estfun` | survreg or coxph fitted with weights, then a sandwich covariance |
| `sandwich@2.5-0#7` | `vcovHC` | multivariate lm only; off-diagonal blocks, diagonal unaffected |
| `sf@0.5-3#9` | `st_union`, `st_difference`, `st_sym_difference` | st_union, st_difference, st_sym_difference in 0.5-2 only |
| `sf@1.0-1#0` | `st_intersection` | st_intersection with the s2 engine active (the default from 1.0-0) |
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

## Yield by package

Changelog candor varies enormously, and a package with no candidates has
not been shown to be correct. Both columns travel together for that
reason.

| package | entries parsed | exposed candidates |
|---|---|---|
| `survival` | 585 | 47 |
| `psych` | 1574 | 37 |
| `cobalt` | 329 | 32 |
| `mgcv` | 955 | 28 |
| `fixest` | 769 | 27 |
| `igraph` | 1014 | 17 |
| `caret` | 750 | 15 |
| `car` | 422 | 11 |
| `forecast` | 567 | 11 |
| `plm` | 578 | 11 |
| `xts` | 249 | 10 |
| `sf` | 557 | 8 |
| `Hmisc` | 637 | 7 |
| `emmeans` | 549 | 7 |
| `lme4` | 352 | 7 |
| `MatchIt` | 191 | 6 |
| `brms` | 850 | 6 |
| `rms` | 699 | 6 |
| `Matrix` | 648 | 5 |
| `randomForest` | 134 | 5 |
| `sjmisc` | 170 | 5 |
| `zoo` | 302 | 5 |
| `VGAM` | 982 | 4 |
| `ordinal` | 120 | 4 |
| `sandwich` | 100 | 4 |
| `AER` | 73 | 3 |
| `MASS` | 148 | 3 |
| `clubSandwich` | 85 | 3 |
| `effects` | 164 | 3 |
| `estimatr` | 73 | 3 |
| `geosphere` | 15 | 3 |
| `mice` | 516 | 3 |
| `miceadds` | 166 | 3 |
| `sampleSelection` | 40 | 3 |
| `stringdist` | 121 | 3 |
| `tmap` | 238 | 3 |
| `e1071` | 154 | 2 |
| `factoextra` | 178 | 2 |
| `lfe` | 60 | 2 |
| `lmtest` | 57 | 2 |
| `margins` | 129 | 2 |
| `nlme` | 585 | 2 |
| `survey` | 15 | 2 |
| `Amelia` | 67 | 1 |
| `MuMIn` | 395 | 1 |
| `ROCR` | 12 | 1 |
| `coin` | 319 | 1 |
| `did` | 119 | 1 |
| `ggeffects` | 274 | 1 |
| `marginaleffects` | 545 | 1 |
| `network` | 252 | 1 |
| `optmatch` | 147 | 1 |
| `questionr` | 89 | 1 |
| `rstan` | 206 | 1 |
| `rstanarm` | 115 | 1 |
| `sjlabelled` | 79 | 1 |
| `strucchange` | 46 | 1 |
| `BayesTree` | 0 | 0 |
| `CBPS` | 1 | 0 |
| `DescTools` | 838 | 0 |
| `FindIt` | 0 | 0 |
| `MCMCpack` | 0 | 0 |
| `Matching` | 28 | 0 |
| `PanelMatch` | 0 | 0 |
| `R2jags` | 0 | 0 |
| `WDI` | 45 | 0 |
| `aod` | 59 | 0 |
| `arm` | 0 | 0 |
| `bayesplot` | 159 | 0 |
| `betareg` | 68 | 0 |
| `boot` | 182 | 0 |
| `brglm` | 0 | 0 |
| `broom.mixed` | 61 | 0 |
| `cem` | 22 | 0 |
| `cjoint` | 0 | 0 |
| `classInt` | 11 | 0 |
| `clusterSEs` | 0 | 0 |
| `coda` | 0 | 0 |
| `cshapes` | 0 | 0 |
| `ebal` | 26 | 0 |
| `erer` | 0 | 0 |
| `ergm` | 755 | 0 |
| `fields` | 0 | 0 |
| `ggmap` | 21 | 0 |
| `glmnet` | 98 | 0 |
| `grf` | 0 | 0 |
| `gsynth` | 11 | 0 |
| `interflex` | 29 | 0 |
| `irr` | 0 | 0 |
| `lavaan` | 0 | 0 |
| `lmerTest` | 31 | 0 |
| `logistf` | 16 | 0 |
| `ltm` | 116 | 0 |
| `mapdata` | 0 | 0 |
| `mediation` | 4 | 0 |
| `memisc` | 134 | 0 |
| `metafor` | 669 | 0 |
| `mfx` | 7 | 0 |
| `mlogit` | 113 | 0 |
| `msm` | 283 | 0 |
| `multcomp` | 3 | 0 |
| `multiwayvcov` | 3 | 0 |
| `mvtnorm` | 63 | 0 |
| `naniar` | 227 | 0 |
| `nnet` | 17 | 0 |
| `pastecs` | 0 | 0 |
| `polycor` | 18 | 0 |
| `pscl` | 0 | 0 |
| `psy` | 0 | 0 |
| `pwr` | 9 | 0 |
| `random` | 41 | 0 |
| `raster` | 15 | 0 |
| `rddensity` | 0 | 0 |
| `rdrobust` | 0 | 0 |
| `rgenoud` | 70 | 0 |
| `rjags` | 0 | 0 |
| `rmeta` | 0 | 0 |
| `rpart` | 32 | 0 |
| `rworldmap` | 0 | 0 |
| `sensemakr` | 0 | 0 |
| `sna` | 16 | 0 |
| `sp` | 57 | 0 |
| `spatstat` | 3630 | 0 |
| `spdep` | 109 | 0 |
| `srvyr` | 83 | 0 |
| `statnet` | 0 | 0 |
| `survminer` | 201 | 0 |
| `systemfit` | 29 | 0 |
| `tidycensus` | 53 | 0 |
| `tseries` | 306 | 0 |
| `weights` | 13 | 0 |

**74** of 131 packages yielded no exposed candidate at all.

