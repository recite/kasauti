# lfe::felm -- 245 corpus scripts, the highest-reach function in the frame.
#
# A battery probe rather than a bug reproducer: it makes an ordinary call with
# ordinary options and dumps everything, so a sweep can find any release where
# the answer moved, whether or not NEWS mentions one.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(lfe)

body <- function(data_path) {
  d <- read.csv(data_path)
  d$fe1 <- factor(d$fe1)
  d$fe2 <- factor(d$fe2)
  d$cl <- factor(d$cl)

  # Two-way fixed effects with one-way clustering: the shape the corpus uses
  # felm for, and the shape lfe's own most consequential fix touched.
  fit <- lfe::felm(y ~ x1 + x2 | fe1 + fe2 | 0 | cl, data = d)

  list(
    quantities = c(
      cc_flatten(coef(fit), "coef"),
      cc_flatten(vcov(fit), "vcov"),
      cc_flatten(as.numeric(fit$rse), "rse")
    ),
    diagnostics = list(
      control = length(coef(fit)) == 2L && nlevels(d$fe1) > 1L && nlevels(d$fe2) > 1L,
      control_says = "felm() absorbed two crossed fixed effects and clustered on a third grouping"
    )
  )
}

cc_main("lfe/felm", "sweep", body, packages = c("lfe"))
