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
  by_package <- tapply(closed$closed_documented, closed$package, mean)
  say(
    "overall: ", sum(closed$closed_documented), " of ", nrow(closed),
    sprintf(" (%.0f%%)", 100 * mean(closed$closed_documented))
  )
  say("\nby package (the unit that clusters):")
  print(round(by_package, 3))

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
  surv <- Surv(pmax(fit_rows$lower_days, 0.5), upper, type = "interval2")

  km <- survfit(surv ~ 1)
  say("Turnbull estimate of the distribution of episode length (days):")
  print(km)

  say("\nobserved spans, in days:")
  print(summary(fit_rows$lower_days))

  if (length(unique(fit_rows$package)) > 1L) {
    # A shared frailty by package: episodes from one library share a hazard.
    # Fitted alongside the bootstrap above rather than instead of it, because a
    # frailty term leans on a parametric random effect a bootstrap does not.
    frailty_fit <- try(
      survreg(surv ~ frailty(factor(package)), dist = "weibull"),
      silent = TRUE
    )
    if (!inherits(frailty_fit, "try-error")) {
      say("\nWeibull AFT with a package frailty term:")
      print(summary(frailty_fit))
    } else {
      say("\nthe frailty model did not converge on this many episodes")
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
  say("largest relative difference per change point:")
  print(summary(changes$max_reldiff))
  say(
    "\n", sum(changes$max_reldiff > 0.01), " of ", nrow(changes),
    " change(s) moved a number by more than 1%"
  )
  say(
    sum(changes$exact == 1), " of ", nrow(changes),
    " are pinned to a single release; the rest span a build failure"
  )
}

say("\ndone")
