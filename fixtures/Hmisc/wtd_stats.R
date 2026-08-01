# Hmisc weighted estimators -- wtd.mean, wtd.var, wtd.quantile.
#
# Not the top of the battery by call volume, but the only Hmisc functions in it
# that produce an estimate rather than an imputation or a reshaped frame. They
# are probed together because they share a weighting convention, and a change to
# that convention should show up in all three at once -- which is a signature a
# single-function probe could not see.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
suppressPackageStartupMessages(library(Hmisc))

body <- function(data_path) {
  d <- read.csv(data_path)
  complete <- d[!is.na(d$y), ]

  quantiles <- Hmisc::wtd.quantile(
    complete$y, weights = complete$w, probs = c(0.1, 0.25, 0.5, 0.75, 0.9)
  )

  list(
    quantities = c(
      list(
        wtd.mean = Hmisc::wtd.mean(complete$y, weights = complete$w),
        wtd.var = Hmisc::wtd.var(complete$y, weights = complete$w),
        # The unweighted values beside them: if only the weighted ones move,
        # the change is in the weighting rather than in the arithmetic.
        mean = mean(complete$y),
        var = stats::var(complete$y)
      ),
      cc_flatten(quantiles, "wtd.quantile")
    ),
    diagnostics = list(
      control = length(unique(complete$w)) > 1L &&
        abs(Hmisc::wtd.mean(complete$y, weights = complete$w) - mean(complete$y)) > 1e-9,
      control_says = "the weights vary and the weighted mean differs from the unweighted one"
    )
  )
}

cc_main("Hmisc/wtd", "sweep", body, packages = c("Hmisc"))
