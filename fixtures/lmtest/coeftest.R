# lmtest::coeftest -- 120 corpus scripts, second only to felm in reach.
#
# The function almost every applied paper reaches for to print a coefficient
# table with a chosen covariance. It sits directly between an estimate and what
# gets published, so a change here moves a printed number by construction.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(lmtest)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- lm(y ~ x1 + x2, data = d)

  # The default covariance and a supplied one, because they travel different
  # paths through coeftest and a change could touch either.
  plain <- lmtest::coeftest(fit)
  supplied <- lmtest::coeftest(fit, vcov. = stats::vcov(fit) * 1.0)

  list(
    quantities = c(
      cc_flatten(plain[, , drop = FALSE], "plain"),
      cc_flatten(supplied[, , drop = FALSE], "supplied")
    ),
    diagnostics = list(
      control = nrow(plain) == 3L && ncol(plain) == 4L,
      control_says = "coeftest() returned a 3-coefficient table with estimate, error, statistic, and p-value"
    )
  )
}

cc_main("lmtest/coeftest", "sweep", body, packages = c("lmtest"))
