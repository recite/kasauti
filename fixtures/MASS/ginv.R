# MASS::ginv -- 31 corpus scripts.
#
# The generalised inverse is reached for precisely when the ordinary one does not
# exist, so the fixture supplies a rank-deficient matrix rather than hoping for
# one: `x3` is exactly `x1 + x2`, and the control checks the rank really is short.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(MASS)

body <- function(data_path) {
  d <- read.csv(data_path)
  design <- as.matrix(cbind(1, d[, c("x1", "x2", "x3")]))
  cross <- crossprod(design)
  inverse <- MASS::ginv(cross)

  list(
    quantities = c(
      cc_flatten(inverse, "ginv"),
      # The defining identity: A G A = A. Reported so the case adjudicates
      # itself -- a change that breaks it is wrong, not merely different.
      cc_flatten(cross %*% inverse %*% cross - cross, "residual")
    ),
    diagnostics = list(
      control = qr(cross)$rank < ncol(cross),
      control_says = paste0(
        "the matrix is rank ", qr(cross)$rank, " of ", ncol(cross),
        ", so ginv() is not solve()"
      )
    )
  )
}

cc_main("MASS/ginv", "sweep", body, packages = c("MASS"))
