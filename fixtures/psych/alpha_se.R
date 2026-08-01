# psych@1.6.4#22 -- the standard error alpha() reports.
#
# "any alpha() call reporting a standard error"
#
# Complete cases only, so this screen isolates the standard error from the
# missing-data handling two other psych claims are about.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(psych)

body <- function(data_path) {
  d <- na.omit(read.csv(data_path))
  a <- suppressWarnings(psych::alpha(d))

  list(
    quantities = cc_flatten(a$total, "total"),
    diagnostics = list(
      control = !anyNA(d) && !is.null(a$total) && length(a$total) > 0,
      control_says = "alpha() ran on complete data and returned its total block"
    )
  )
}

cc_main("psych@1.6.4#22", "screen", body, packages = c("psych"))
