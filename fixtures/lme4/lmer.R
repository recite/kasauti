# lme4::lmer -- 33 corpus scripts, the standard mixed model in this corpus.
#
# The fixed effects, the variance components, and the log-likelihood all travel,
# because they fail differently: a changed optimiser moves the variance
# components while barely touching the fixed effects, and a changed likelihood
# parameterisation moves all three.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
suppressPackageStartupMessages(library(lme4))

body <- function(data_path) {
  d <- read.csv(data_path)
  d$g <- factor(d$g)
  fit <- lme4::lmer(y ~ x1 + x2 + (1 | g), data = d, REML = FALSE)

  variances <- as.data.frame(lme4::VarCorr(fit))

  list(
    quantities = c(
      cc_flatten(lme4::fixef(fit), "fixef"),
      cc_flatten(diag(as.matrix(stats::vcov(fit))), "var"),
      cc_flatten(
        stats::setNames(variances$vcov, paste0(variances$grp, ".", variances$var1)),
        "vc"
      ),
      list(logLik = as.numeric(stats::logLik(fit)))
    ),
    diagnostics = list(
      # A variance component at zero is a boundary fit, where optimisers
      # disagree for reasons that are not the question. The control refuses it.
      control = nlevels(d$g) >= 10L && min(variances$vcov) > 1e-8,
      control_says = paste0(
        "lmer() fitted ", nlevels(d$g),
        " groups with every variance component away from the boundary"
      )
    )
  )
}

cc_main("lme4/lmer", "sweep", body, packages = c("lme4"))
