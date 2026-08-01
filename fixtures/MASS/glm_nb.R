# MASS::glm.nb -- 29 corpus scripts.
#
# An iteratively fitted dispersion parameter, which is where a negative binomial
# has room to disagree with itself across versions: theta and the coefficients
# are estimated in alternation, so a change to either convergence rule moves
# both.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(MASS)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- MASS::glm.nb(count ~ x1 + x2, data = d)

  list(
    quantities = c(
      cc_flatten(coef(fit), "coef"),
      cc_flatten(diag(stats::vcov(fit)), "var"),
      list(
        theta = as.numeric(fit$theta),
        se.theta = as.numeric(fit$SE.theta),
        twologlik = as.numeric(fit$twologlik),
        iterations = as.numeric(fit$iter)
      )
    ),
    diagnostics = list(
      # A theta that ran away to the Poisson limit would mean the fixture is not
      # overdispersed and the negative binomial path was never really exercised.
      control = is.finite(fit$theta) && fit$theta < 1e4 && fit$converged,
      control_says = paste0(
        "glm.nb() converged with a finite dispersion, theta = ",
        signif(fit$theta, 4)
      )
    )
  )
}

cc_main("MASS/glm.nb", "sweep", body, packages = c("MASS"))
