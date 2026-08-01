# psych@2.4.4#42 -- alpha() deriving the correlation matrix through cov2cor.
#
# "alpha() deriving the correlation matrix indirectly through cov2cor"
#
# Handing alpha() a covariance matrix rather than raw data is what forces that
# path, so the control checks the input really is one: unequal diagonal entries,
# which a correlation matrix cannot have.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(psych)

body <- function(data_path) {
  d <- read.csv(data_path)
  covariance <- stats::cov(d, use = "pairwise.complete.obs")
  a <- suppressWarnings(psych::alpha(covariance))

  list(
    quantities = cc_flatten(a$total, "total"),
    diagnostics = list(
      control = length(unique(round(diag(covariance), 8))) > 1L,
      control_says = "alpha() was given a covariance matrix, not a correlation matrix"
    )
  )
}

cc_main("psych@2.4.4#42", "screen", body, packages = c("psych"))
