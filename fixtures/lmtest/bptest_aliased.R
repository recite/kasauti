# lmtest@0.9-35#2 -- bptest() on a fit with aliased regressors.
#
# "aliased or collinear regressors"
#
# The full fit is rank deficient by construction, so `lm` aliases a coefficient
# to NA. The well-conditioned fit is screened beside it: if only the aliased one
# moves, the entry is confirmed as stated rather than as a general change to the
# test.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(lmtest)

body <- function(data_path) {
  d <- read.csv(data_path)
  aliased <- lm(y ~ x1 + x2 + x3, data = d)
  clean <- lm(y ~ x1 + x2, data = d)

  report <- function(test, prefix) {
    stats::setNames(
      list(unname(test$statistic), unname(test$parameter), unname(test$p.value)),
      paste0(prefix, c(".statistic", ".parameter", ".p.value"))
    )
  }

  list(
    quantities = c(
      report(lmtest::bptest(aliased), "aliased"),
      report(lmtest::bptest(clean), "clean")
    ),
    diagnostics = list(
      control = anyNA(coef(aliased)),
      control_says = paste0(
        "lm() aliased ", sum(is.na(coef(aliased))),
        " coefficient(s), so bptest() saw a rank-deficient fit"
      )
    )
  )
}

cc_main("lmtest@0.9-35#2", "screen", body, packages = c("lmtest"))
