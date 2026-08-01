# lme4::glmer -- 12 corpus scripts.
#
# The generalised case, where the likelihood has no closed form and is
# approximated. That approximation is a choice, so this is where lme4 has the
# most room to change its answer between releases.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
suppressPackageStartupMessages(library(lme4))

body <- function(data_path) {
  d <- read.csv(data_path)
  d$g <- factor(d$g)
  fit <- lme4::glmer(
    yb ~ x1 + x2 + (1 | g),
    data = d, family = stats::binomial(), nAGQ = 1L
  )
  variances <- as.data.frame(lme4::VarCorr(fit))

  list(
    quantities = c(
      cc_flatten(lme4::fixef(fit), "fixef"),
      cc_flatten(
        stats::setNames(variances$vcov, paste0(variances$grp, ".", variances$var1)),
        "vc"
      ),
      list(logLik = as.numeric(stats::logLik(fit)))
    ),
    diagnostics = list(
      control = length(unique(d$yb)) == 2L && is.finite(stats::logLik(fit)),
      control_says = "glmer() fitted a binary outcome with both levels present and a finite likelihood"
    )
  )
}

cc_main("lme4/glmer", "sweep", body, packages = c("lme4"))
