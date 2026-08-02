# The four estimands, from the two tidy tables the sweep produces.
#
# Run as an ordinary process, like every backend in this project:
#   Rscript --vanilla analysis/estimands.R [data-dir] [out-dir]
#
# R rather than Python because interval-censored duration models with a random
# effect are native here and reimplementing them would be a second, worse copy.
# Nothing below needs a package outside base R and `survival`, deliberately: an
# analysis that cannot be re-run without a dependency resolver is not the
# reproducible half of a reproducible pipeline.
#
# Three things this script refuses to do, each of which would shorten every
# estimate it produces:
#
#   * drop right-censored episodes. A value still holding at the last release may
#     be correct and permanent or wrong and undiscovered; dropping them conditions
#     the answer on eventual change.
#   * treat a left-censored episode as if it began at the buildability floor. It
#     began before it, and how much before is unknown.
#   * report one number per episode without acknowledging that episodes cluster
#     within packages. A package is one maintainer, one codebase, and one habit
#     of writing NEWS.
#
# And one more, found by counting: probes are not independent within a release.
# Two `estimatr` probes both call `difference_in_means`, so a release that
# changed it produces two change points describing one event. 24 probe-level
# changes here collapse to 18 distinct (package, release) changes. Rates and
# documented shares are therefore computed on the collapsed unit and the
# probe-level count is shown beside it, never instead of it.

suppressPackageStartupMessages(library(survival))

args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) >= 1) args[[1]] else "data"
out_dir <- if (length(args) >= 2) args[[2]] else "docs"
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

changes <- read.csv(file.path(data_dir, "changes.csv"), stringsAsFactors = FALSE)
episodes <- read.csv(file.path(data_dir, "episodes.csv"), stringsAsFactors = FALSE)
builds <- read.csv(file.path(data_dir, "builds.csv"), stringsAsFactors = FALSE)

say <- function(...) cat(..., "\n", sep = "")
rule <- function(title) say("\n", title, "\n", strrep("-", nchar(title)))

# ---------------------------------------------------------------- coverage ----
# Reported first and never as a footnote. Every estimate below is conditional on
# what could be built and run, and that share varies enormously by package.

rule("Coverage")

per_package <- do.call(rbind, lapply(split(episodes, episodes$package), function(d) {
  data.frame(
    package = d$package[[1]],
    probes = length(unique(d$probe)),
    episodes = nrow(d),
    closed = sum(d$end == "CLOSED"),
    left_censored = sum(d$start == "LEFT_CENSORED"),
    stringsAsFactors = FALSE
  )
}))

reach <- do.call(rbind, lapply(split(builds, builds$package), function(d) {
  data.frame(
    package = d$package[[1]],
    tried = nrow(d),
    built = sum(d$outcome == "BUILT"),
    buildable = sum(d$outcome == "BUILT") / nrow(d),
    stringsAsFactors = FALSE
  )
}))

coverage <- merge(per_package, reach, by = "package", all.x = TRUE)
print(coverage, row.names = FALSE)

say(
  "\n", nrow(episodes), " episode(s) across ", nrow(per_package), " package(s); ",
  sum(episodes$end == "CLOSED"), " closed, ",
  sum(episodes$start == "LEFT_CENSORED"), " already in force at the floor."
)

# ------------------------------------------------------- E1: change rate ----
# How often does a package change your answer? Counted per probe-year of
# observed history, so a package with a long swept history is not credited with
# more changes merely for being old.

rule("E1  Result-changing releases per probe-year")

# Every dated endpoint, including the last release known to hold the final value.
# Using only opened_on and closed_on collapses the span whenever the newest
# episode is right-censored -- which it always is -- and that inflated estimatr's
# rate forty-fold before it was caught.
span_years <- function(d) {
  dates <- as.Date(c(d$opened_on, d$closed_on, d$closed_after_on))
  dates <- dates[!is.na(dates)]
  if (length(dates) < 2L) return(NA_real_)
  as.numeric(diff(range(dates))) / 365.25
}

rates <- do.call(rbind, lapply(split(episodes, episodes$package), function(d) {
  years <- span_years(d)
  data.frame(
    package = d$package[[1]],
    probes = length(unique(d$probe)),
    years = years,
    changes = sum(d$end == "CLOSED"),
    per_probe_year = sum(d$end == "CLOSED") / (years * length(unique(d$probe))),
    stringsAsFactors = FALSE
  )
}))
print(rates, row.names = FALSE)

if (sum(!is.na(rates$per_probe_year)) > 1L) {
  # A package-level mean, not an episode-level one. Pooling episodes would weight
  # a package with many probes as if it were many packages, which is the
  # clustering mistake this whole section exists to avoid.
  say(
    "\nmean across packages: ",
    sprintf("%.3f", mean(rates$per_probe_year, na.rm = TRUE)),
    " change(s) per probe-year"
  )
}

# --------------------------------------------------- E2: documented share ----
# The estimand the sweep exists for. A change point the changelog does not
# mention is invisible to any study that starts from changelogs, so its share
# cannot be estimated from within that frame at all.

rule("E2  Share of closing changes the changelog names")

closed <- episodes[episodes$end == "CLOSED", ]
if (nrow(closed) > 0L) {
  # Collapse to the release. Two probes calling the same function report one
  # event twice, and counting both would shrink the interval on a number whose
  # whole point is honesty about what the changelog omits.
  key <- paste(closed$package, closed$closed)
  collapsed <- do.call(rbind, lapply(split(closed, key), function(d) {
    data.frame(
      package = d$package[[1]],
      release = d$closed[[1]],
      probes = nrow(d),
      # Any probe finding it documented settles it: the question is whether the
      # maintainer described the change, not whether every probe noticed.
      documented = as.integer(any(d$closed_documented == 1)),
      stringsAsFactors = FALSE
    )
  }))

  say(
    "probe-level: ", sum(closed$closed_documented), " of ", nrow(closed),
    sprintf(" (%.0f%%)", 100 * mean(closed$closed_documented))
  )
  say(
    "release-level (the independent unit): ", sum(collapsed$documented), " of ",
    nrow(collapsed), sprintf(" (%.0f%%)", 100 * mean(collapsed$documented))
  )
  say(
    "  ", nrow(closed) - nrow(collapsed),
    " probe-level change(s) describe an event another probe also saw"
  )

  closed <- collapsed
  closed$closed_documented <- collapsed$documented
  by_package <- tapply(closed$closed_documented, closed$package, mean)
  say("\nby package (the unit that clusters):")
  print(round(by_package, 3))
  say(
    "\nThe documented flag counts a match on any function the probe declares, ",
    "and a probe\nexercising three functions declares three. That biases it ",
    "toward documented, so the\nundocumented share is a lower bound."
  )

  # Cluster bootstrap over packages rather than a binomial interval over
  # episodes. Episodes within a package are not independent draws -- one
  # maintainer's habit of writing NEWS produces all of them.
  packages <- unique(closed$package)
  if (length(packages) > 1L) {
    set.seed(1L)
    draws <- replicate(2000L, {
      picked <- sample(packages, length(packages), replace = TRUE)
      rows <- do.call(rbind, lapply(picked, function(p) closed[closed$package == p, ]))
      mean(rows$closed_documented)
    })
    say(
      "\ncluster bootstrap over packages: ",
      sprintf(
        "%.0f%% [%.0f%%, %.0f%%]",
        100 * mean(closed$closed_documented),
        100 * quantile(draws, 0.025), 100 * quantile(draws, 0.975)
      )
    )
  } else {
    say("\nonly one package has closed episodes; no cluster interval is possible")
  }
}

# --------------------------------------------------------- E3: durations ----
# Interval-censored throughout. `lower_days` is what certainly elapsed and
# `upper_days` what may have; where a build failure sits inside a bounding
# interval the two differ, and the model is told rather than being handed a
# midpoint that was never observed.

rule("E3  How long a value held")

fit_rows <- episodes[!is.na(episodes$lower_days), ]
if (nrow(fit_rows) > 0L) {
  # Surv(type = "interval2"): NA on the right marks right-censoring, which is
  # exactly the encoding an episode still running at the last release wants.
  upper <- ifelse(fit_rows$end == "CLOSED", fit_rows$upper_days, NA)
  # The response lives in the data frame rather than in the calling environment,
  # so `data =` can resolve `package` for the frailty term. Building it outside
  # and relying on scoping reported "did not converge" for what was a missing
  # argument -- a wrong answer that looked like a finding about the sample.
  fit_rows$span <- Surv(pmax(fit_rows$lower_days, 0.5), upper, type = "interval2")
  surv <- fit_rows$span

  km <- survfit(surv ~ 1)
  say("Turnbull estimate of the distribution of episode length (days):")
  print(km)

  say("\nobserved spans, in days:")
  print(summary(fit_rows$lower_days))

  if (length(unique(fit_rows$package)) > 1L) {
    # A shared frailty by package: episodes from one library share a hazard.
    # Fitted alongside the bootstrap above rather than instead of it, because a
    # frailty term leans on a parametric random effect a bootstrap does not.
    # Package as a *fixed* effect, not a frailty. Two reasons, and the second is
    # the real one: `survreg` does not implement frailty terms at all (only
    # `coxph` does, and `coxph` in turn does not take interval censoring), and a
    # variance component estimated from six clusters would be barely identified
    # even if it did. Fixed effects at this width are the honest choice; a
    # random effect becomes worth reaching for when the package count grows.
    fixed <- try(
      survreg(span ~ factor(package), data = fit_rows, dist = "weibull"),
      silent = TRUE
    )
    if (!inherits(fixed, "try-error")) {
      say("\nWeibull AFT with package fixed effects:")
      print(summary(fixed))
    } else {
      say("\nthe accelerated-failure-time model did not fit:")
      say(as.character(fixed))
    }

    # A median with a cluster interval, resampling packages rather than
    # episodes. Reported beside the frailty rather than instead of it: the
    # frailty leans on a parametric random effect this does not.
    set.seed(1L)
    packages <- unique(fit_rows$package)
    medians <- replicate(1000L, {
      picked <- sample(packages, length(packages), replace = TRUE)
      rows <- do.call(rbind, lapply(picked, function(p) {
        fit_rows[fit_rows$package == p, ]
      }))
      # The median of a Turnbull curve is undefined whenever the resample never
      # falls below 0.5 -- with heavy right-censoring that happens often, and
      # those resamples are dropped rather than filled in. How many survived is
      # printed, because a bootstrap that mostly failed is not an interval.
      drawn <- try(
        as.numeric(quantile(survfit(rows$span ~ 1), probs = 0.5)$quantile),
        silent = TRUE
      )
      if (inherits(drawn, "try-error") || length(drawn) != 1L) NA_real_ else drawn
    })
    medians <- medians[!is.na(medians)]
    if (length(medians) > 50L) {
      say(
        "\nmedian episode length, cluster bootstrap over packages: ",
        sprintf(
          "%.0f days [%.0f, %.0f] from %d resample(s)",
          median(medians), quantile(medians, 0.025), quantile(medians, 0.975),
          length(medians)
        )
      )
    } else {
      # Said out loud rather than silently omitted. Too few resamples reach a
      # median means the censoring is heavy enough that this sample cannot
      # support an interval on it, which is itself worth knowing.
      say(
        "\nmedian episode length: only ", length(medians), " of 1000 resample(s) ",
        "reached a median, so no cluster interval is reported. ",
        "Right-censoring is too heavy at this sample size."
      )
    }
  } else {
    say("\none package only; a frailty term is not identified")
  }
} else {
  say("no episode has a datable span yet")
}

# ---------------------------------------------- E4: magnitude of a change ----
# Whether a change is worth a reader's attention is not the same question as
# whether it happened. A relative difference of 1e-7 and one of 1.7 are both
# change points and only one of them moves a published table.

rule("E4  How large the changes were")

if (nrow(changes) > 0L) {
  # A shape change carries max_reldiff = 0 because nothing shared moved: the
  # function began returning a quantity it had not returned before. Pooling it
  # with the numeric changes would drag the summary toward zero and read as
  # noise, so it is counted apart.
  shape <- changes[changes$shape_only == 1, ]
  numeric_changes <- changes[changes$shape_only == 0, ]

  say(
    nrow(shape), " of ", nrow(changes),
    " change(s) are a quantity appearing or vanishing rather than moving"
  )
  say("\nlargest relative difference, numeric changes only:")
  print(summary(numeric_changes$max_reldiff))
  say(
    "\n", sum(numeric_changes$max_reldiff > 0.01), " of ", nrow(numeric_changes),
    " numeric change(s) moved a number by more than 1%"
  )
  say(
    sum(changes$exact == 1), " of ", nrow(changes),
    " are pinned to a single release; the rest span a build failure"
  )
}

# ------------------------------------------------- E5: response latency ----
# How long between somebody reporting a defect and a release carrying the fix.
# The only one of these estimands that needs no archived build, so it reaches
# packages the sweep cannot -- and it is conditional on something the others are
# not, which is stated rather than buried.

rule("E5  Report to release")

flagged_path <- file.path(data_dir, "flagged.csv")
if (file.exists(flagged_path)) {
  flags <- read.csv(flagged_path, stringsAsFactors = FALSE)
  usable <- flags[flags$plausible == 1 & !is.na(flags$response_days), ]

  say(
    nrow(flags), " citation(s); ", sum(!is.na(flags$response_days)),
    " resolved to an issue; ", nrow(usable), " precede their release and are usable."
  )
  say(
    "\nA citation that does not precede its release is not an issue in that ",
    "repository --\nit is a version, a pull request, or somebody else's ticket. ",
    "Those are kept in the\ntable flagged rather than dropped, so the share that ",
    "is noise stays visible."
  )

  if (nrow(usable) > 0L) {
    say("\ndays from report to release:")
    print(summary(usable$response_days))

    by_package <- tapply(usable$response_days, usable$package, median)
    say("\nmedian by package (the unit that clusters):")
    print(round(by_package[order(by_package)], 1))

    packages <- unique(usable$package)
    if (length(packages) > 1L) {
      set.seed(1L)
      draws <- replicate(2000L, {
        picked <- sample(packages, length(packages), replace = TRUE)
        rows <- do.call(rbind, lapply(picked, function(p) {
          usable[usable$package == p, ]
        }))
        median(rows$response_days)
      })
      say(
        "\nmedian, cluster bootstrap over packages: ",
        sprintf(
          "%.0f days [%.0f, %.0f]",
          median(usable$response_days),
          quantile(draws, 0.025), quantile(draws, 0.975)
        )
      )
    }

    # The gate this estimand carries and the others do not. A package that
    # develops privately contributes nothing here, and packages that develop in
    # the open are not a random half of CRAN.
    say(
      "\nEvery number above is conditional on the package naming a public GitHub ",
      "repository\non CRAN. Packages developing privately -- MASS, sandwich, ",
      "lmtest, Hmisc among them --\ncontribute nothing, and they are not a random ",
      "half of the frame."
    )
  }
} else {
  say("data/flagged.csv is not present; run `kasauti flagged`")
}

say("\ndone")
