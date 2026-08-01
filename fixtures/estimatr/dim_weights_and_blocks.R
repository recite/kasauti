# estimatr@0.6.0#11 -- weights and blocks supplied together.
#
# "both weights and blocks supplied"
#
# Either alone works; the entry is about the combination, so the control checks
# that both really varied. Equal weights, or one block, would leave the fixture
# exercising the ordinary path under a name that sounds like the special one.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(estimatr)

body <- function(data_path) {
  d <- read.csv(data_path)
  # Two arms, so the estimand is unambiguous and only the weights-with-blocks
  # combination is under test.
  d <- d[d$z %in% c(0, 1), ]
  fit <- estimatr::difference_in_means(
    y ~ z,
    data = d,
    weights = d$w,
    blocks = d$block
  )

  list(
    quantities = list(
      estimate = unname(fit$coefficients[[1]]),
      std.error = unname(fit$std.error[[1]]),
      statistic = unname(fit$statistic[[1]]),
      p.value = unname(fit$p.value[[1]]),
      df = unname(fit$df[[1]])
    ),
    diagnostics = list(
      control = length(unique(d$w)) > 1L && length(unique(d$block)) > 1L,
      control_says = paste0(
        "difference_in_means() had ", length(unique(d$block)),
        " blocks and unequal weights at once"
      )
    )
  )
}

cc_main("estimatr@0.6.0#11", "screen", body, packages = c("estimatr"))
