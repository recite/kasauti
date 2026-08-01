# car::deltaMethod -- 15 corpus scripts.
#
# Propagating a coefficient covariance through a nonlinear function, which is
# where an implementation has to differentiate something -- numerically or
# symbolically -- and therefore where two versions can quietly disagree.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(car)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- lm(y ~ x1 + x2 + x3, data = d)

  ratio <- car::deltaMethod(fit, "x1 / x2")
  product <- car::deltaMethod(fit, "x1 * x3")

  numbers <- function(result, prefix) {
    frame <- as.data.frame(result)
    keep <- vapply(frame, is.numeric, logical(1))
    cc_flatten(frame[, keep, drop = FALSE], prefix)
  }

  list(
    quantities = c(numbers(ratio, "ratio"), numbers(product, "product")),
    diagnostics = list(
      control = abs(coef(fit)[["x2"]]) > 0.5 && is.finite(ratio[1, 1]),
      control_says = "deltaMethod() propagated through a ratio whose denominator is well away from zero"
    )
  )
}

cc_main("car/deltaMethod", "sweep", body, packages = c("car"))
