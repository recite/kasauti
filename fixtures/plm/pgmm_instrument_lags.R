# plm@1.2-6#1 -- GMM instruments built with different lags.
#
# "different lags for GMM instruments"
#
# The dynamic panel the fixture generates is what makes this testable: without a
# lagged dependent variable there is nothing for the instrument matrix to be
# built from, and the claim would be unreachable.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(plm)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- plm::pgmm(
    y ~ lag(y, 1) + x1 | lag(y, 2:4),
    data = d,
    index = c("id", "year"),
    effect = "individual",
    model = "twosteps"
  )

  list(
    quantities = c(
      cc_flatten(coef(fit), "coef"),
      cc_flatten(diag(vcov(fit)), "var")
    ),
    diagnostics = list(
      # The lag range in the instrument block is the condition. A single lag
      # would exercise a different code path from the one the entry names.
      control = length(coef(fit)) > 1L && is.finite(coef(fit)[[1]]),
      control_says = "pgmm() fitted with instruments at lags 2:4, a range rather than one lag"
    )
  )
}

cc_main("plm@1.2-6#1", "screen", body, packages = c("plm"))
