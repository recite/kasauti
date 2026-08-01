# MASS::mvrnorm -- 54 corpus scripts.
#
# The only probe in the battery that draws from the RNG, which makes it the one
# that needs saying out loud: the seed is fixed, so two package versions see the
# same stream and any difference is the package. What this cannot separate is a
# change in *how* mvrnorm consumes the stream from a change in what it returns --
# and it should not, because both change the numbers a user gets from the same
# seeded script, which is the question.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(MASS)

body <- function(data_path) {
  d <- read.csv(data_path)
  sigma <- stats::cov(d[, c("x1", "x2", "y")])
  mu <- colMeans(d[, c("x1", "x2", "y")])

  # RNGkind pinned as well as the seed: R's default generator has changed
  # before, and a sweep that let it float would attribute R's history to MASS.
  suppressWarnings(RNGkind(kind = "Mersenne-Twister", normal.kind = "Inversion"))
  set.seed(20260801)
  drawn <- MASS::mvrnorm(n = 40, mu = mu, Sigma = sigma)

  list(
    quantities = c(
      cc_flatten(colMeans(drawn), "mean"),
      cc_flatten(stats::cov(drawn), "cov")
    ),
    diagnostics = list(
      control = nrow(drawn) == 40L && ncol(drawn) == 3L && all(is.finite(drawn)),
      control_says = "mvrnorm() drew 40 finite rows from a 3-dimensional covariance under a pinned seed and generator"
    )
  )
}

cc_main("MASS/mvrnorm", "sweep", body, packages = c("MASS"))
