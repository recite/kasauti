# car::linearHypothesis -- 30 corpus scripts.
#
# The general test of linear restrictions, and the place an applied paper turns a
# fitted model into a reported F. Two restrictions are tested: a single
# coefficient, and a cross-coefficient equality, because they take different
# paths through the hypothesis matrix.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(car)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- lm(y ~ x1 + x2 + x3, data = d)

  single <- car::linearHypothesis(fit, "x1 = 0")
  joint <- car::linearHypothesis(fit, c("x1 = 0", "x2 + x3 = 0"))

  numbers <- function(test, prefix) {
    keep <- vapply(test, is.numeric, logical(1))
    cc_flatten(as.data.frame(test)[, keep, drop = FALSE], prefix)
  }

  list(
    quantities = c(numbers(single, "single"), numbers(joint, "joint")),
    diagnostics = list(
      control = nrow(single) == 2L && nrow(joint) == 2L,
      control_says = "linearHypothesis() returned a restricted-against-unrestricted comparison for both a single and a joint restriction"
    )
  )
}

cc_main("car/linearHypothesis", "sweep", body, packages = c("car"))
