# lfe::getfe -- 30 corpus scripts.
#
# Recovering the absorbed fixed effects, which is a genuinely harder problem than
# the coefficients: they are identified only up to a normalisation, so this is
# where an implementation has room to change its mind.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(lfe)

body <- function(data_path) {
  d <- read.csv(data_path)
  d$fe1 <- factor(d$fe1)
  d$fe2 <- factor(d$fe2)

  fit <- lfe::felm(y ~ x1 + x2 | fe1 + fe2, data = d)
  effects <- lfe::getfe(fit)

  list(
    quantities = cc_flatten(
      stats::setNames(as.numeric(effects$effect), as.character(effects$idx)),
      "fe"
    ),
    diagnostics = list(
      control = nrow(effects) > 2L && all(is.finite(effects$effect)),
      control_says = paste0(
        "getfe() returned ", nrow(effects), " finite fixed-effect estimate(s)"
      )
    )
  )
}

cc_main("lfe/getfe", "sweep", body, packages = c("lfe"))
