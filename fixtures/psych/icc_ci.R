# psych@1.9.12#26 -- the confidence interval ICC() reports.
#
# "any ICC() call reporting confidence intervals; the interval was built at
#  alpha/2 rather than alpha, so coverage was wrong"
#
# Recorded in the sampling-frame notes as the one collision the attribution rules
# do not catch: the `alpha` in that entry is a significance level, not
# `psych::alpha`. It is screened here on its own terms, as an ICC claim.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(psych)

body <- function(data_path) {
  d <- na.omit(read.csv(data_path))
  fit <- psych::ICC(d, alpha = 0.05)
  results <- fit$results

  # The interval bounds are the claim; the point estimates travel with them so a
  # screen can say whether only the interval moved.
  numeric <- results[, vapply(results, is.numeric, logical(1)), drop = FALSE]

  list(
    quantities = cc_flatten(numeric, "icc"),
    diagnostics = list(
      control = any(grepl("lower|upper", tolower(names(results)))),
      control_says = "ICC() returned confidence limits alongside its estimates"
    )
  )
}

cc_main("psych@1.9.12#26", "screen", body, packages = c("psych"))
