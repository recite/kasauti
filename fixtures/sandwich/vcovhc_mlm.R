# sandwich@2.5-0#7 -- vcovHC on a multivariate lm.
#
# "The off-diagonal values of the vcovHC() were computed without preserving the
#  sign of the underlying residuals."
#
# Every screen script has the same four parts: pin the version, fit under the
# stated condition, dump every number the call returned, and state the control
# that proves the condition was met.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(sandwich)

body <- function(data_path) {
  d <- read.csv(data_path)
  m <- lm(cbind(y, y2) ~ x1 + x2, data = d)
  v <- sandwich::vcovHC(m, type = "HC0")

  list(
    quantities = cc_flatten(v, "vcovHC"),
    diagnostics = list(
      # The control is not decoration. Without it, a screen that saw nothing
      # move could not tell "this version is fine" from "the model was never a
      # multivariate lm and vcovHC.mlm never ran".
      control = inherits(m, "mlm") && ncol(coef(m)) == 2L,
      control_says = "lm(cbind(y, y2) ~ .) is a multivariate lm, so vcovHC dispatches to vcovHC.mlm"
    )
  )
}

cc_main("sandwich@2.5-0#7", "screen", body, packages = c("sandwich"))
