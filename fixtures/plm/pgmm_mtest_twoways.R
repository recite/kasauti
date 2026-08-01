# plm@1.2-6#0 -- mtest() after pgmm, and the Wald test for time dummies.
#
# "effect='individual' with transformation='ld', and the Wald test for time
#  dummies under effect='twoways'"
#
# Two conditions in one entry, so both are fitted and both dumped. Which of them
# moves is the first thing a promotion would need to know.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(plm)

body <- function(data_path) {
  d <- read.csv(data_path)
  index <- c("id", "year")

  system <- plm::pgmm(
    y ~ lag(y, 1) + x1 | lag(y, 2:3),
    data = d, index = index,
    effect = "individual", model = "onestep", transformation = "ld"
  )
  twoways <- plm::pgmm(
    y ~ lag(y, 1) + x1 | lag(y, 2:3),
    data = d, index = index,
    effect = "twoways", model = "onestep", transformation = "d"
  )
  m2 <- plm::mtest(system, order = 2L)

  list(
    quantities = c(
      cc_flatten(coef(system), "ld.coef"),
      cc_flatten(coef(twoways), "twoways.coef"),
      list(
        mtest.statistic = unname(m2$statistic),
        mtest.p.value = unname(m2$p.value)
      )
    ),
    diagnostics = list(
      control = is.finite(m2$statistic) && length(coef(twoways)) >= 2L,
      control_says = "pgmm(transformation = 'ld', effect = 'individual') with mtest, beside an effect = 'twoways' fit"
    )
  )
}

cc_main("plm@1.2-6#0", "screen", body, packages = c("plm"))
