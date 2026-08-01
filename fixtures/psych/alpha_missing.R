# psych@2.4.4#3 -- alpha() on data with missing values.
#
# "alpha() on data with missing values, where average R was formed from the
#  covariance rather than the correlation"
#
# The same fixture as the standard-error screen, with the missing cells left in.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(psych)

body <- function(data_path) {
  d <- read.csv(data_path)
  a <- suppressWarnings(psych::alpha(d))

  list(
    quantities = cc_flatten(a$total, "total"),
    diagnostics = list(
      # Missing values are the condition, so their presence is the control.
      # Without it a fixture that silently dropped them would report
      # NOT_TRIGGERED and look like evidence.
      control = anyNA(d) && !is.null(a$total),
      control_says = paste0(
        "alpha() ran on data with ", sum(is.na(d)), " missing cell(s)"
      )
    )
  )
}

cc_main("psych@2.4.4#3", "screen", body, packages = c("psych"))
