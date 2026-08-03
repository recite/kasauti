# fixest and singleton fixed effects.
#
# A singleton is a fixed-effect level holding exactly one observation. Its own
# dummy fits it perfectly, so it adds no identifying variation while adding a
# parameter. Every package that absorbs fixed effects has to decide whether to
# keep it, and the decision sets the estimation sample: N, the residual degrees
# of freedom, and the cluster count all move with it -- and every standard error
# in the table moves with them.
#
# So this probe reports the *sample* before it reports the estimates. "N went
# from 260 to 240" is legible on sight; "a coefficient moved 3%" is the same
# event and tells a reader nothing.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
suppressPackageStartupMessages(library(fixest))

# Accessors have come and gone across fixest's history, so each is asked for
# defensively. A quantity that cannot be read is omitted rather than fatal:
# cc_write drops non-finite values, and a probe that died on a renamed field
# would report a version that runs perfectly well as unevaluable.
maybe <- function(expr) {
  value <- tryCatch(suppressWarnings(expr), error = function(e) NA_real_)
  if (length(value) != 1L || !is.numeric(value)) NA_real_ else as.numeric(value)
}

body <- function(data_path) {
  d <- read.csv(data_path)
  d$g <- factor(d$g)
  d$t <- factor(d$t)
  d$cl <- factor(d$cl)
  sizes <- table(d$g)

  fit <- fixest::feols(y ~ x1 + x2 | g + t, data = d, cluster = ~cl)

  list(
    quantities = c(
      list(
        nobs = maybe(stats::nobs(fit)),
        groups.g = maybe(length(unique(fit$fixef_id$g))),
        groups.t = maybe(length(unique(fit$fixef_id$t))),
        fixef.params = maybe(sum(unlist(fit$fixef_sizes))),
        df.residual = maybe(stats::df.residual(fit)),
        clusters = maybe(fit$G[[1]]),
        input.rows = nrow(d),
        input.groups = nlevels(d$g),
        input.singletons = sum(sizes == 1L)
      ),
      cc_flatten(coef(fit), "coef"),
      cc_flatten(sqrt(diag(stats::vcov(fit))), "se")
    ),
    diagnostics = list(
      control = sum(sizes == 1L) > 0L && sum(sizes > 1L) > 0L,
      control_says = paste0(
        nrow(d), " rows over ", nlevels(d$g), " groups, of which ",
        sum(sizes == 1L), " are singletons"
      )
    )
  )
}

cc_main("fixest/singletons", "sweep", body, packages = c("fixest"))
