# estimatr@0.12.0#7 -- subsetting a treatment with more than two conditions.
#
# "condition1/condition2 subsetting a treatment with more than two conditions"
#
# The control checks the treatment really has three arms. On a two-armed
# treatment condition1/condition2 select everything, the code path the entry is
# about is never entered, and a screen would report agreement that means nothing.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(estimatr)

body <- function(data_path) {
  d <- read.csv(data_path)
  d$z <- factor(d$z)
  fit <- estimatr::difference_in_means(
    y ~ z,
    data = d,
    condition1 = "0",
    condition2 = "2"
  )

  list(
    quantities = list(
      estimate = unname(fit$coefficients[[1]]),
      std.error = unname(fit$std.error[[1]]),
      statistic = unname(fit$statistic[[1]]),
      p.value = unname(fit$p.value[[1]]),
      df = unname(fit$df[[1]]),
      conf.low = unname(fit$conf.low[[1]]),
      conf.high = unname(fit$conf.high[[1]])
    ),
    diagnostics = list(
      control = nlevels(d$z) > 2L,
      control_says = paste0(
        "the treatment has ", nlevels(d$z),
        " conditions, so condition1/condition2 genuinely subset it"
      )
    )
  )
}

cc_main("estimatr@0.12.0#7", "screen", body, packages = c("estimatr"))
