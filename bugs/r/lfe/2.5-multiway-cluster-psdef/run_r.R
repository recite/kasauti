source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))
library(lfe)

# No archived install is needed for this one, which is unusual and worth saying.
# The changelog entry ends "Can be switched off by felm(...,psdef=FALSE)", so the
# package still ships the pre-2.5 behaviour behind a flag: one current version
# produces both answers. Where a fix is revertible by argument, archaeology costs
# nothing and cannot be defeated by a package that no longer builds.
flags <- cc_args()$flags
psdef <- !(length(flags) && identical(flags[[1]], "unadjusted"))

body <- function(data_path) {
  d <- read.csv(data_path)
  d$firm <- factor(d$firm)
  d$year <- factor(d$year)

  # Two-way clustering by firm and year. suppressWarnings because the adjusted
  # run announces itself -- "Negative eigenvalues set to zero" -- and that
  # warning is a finding recorded in NOTES.md rather than something to hide:
  # the fix is loud, the behaviour it replaced was not.
  fit <- suppressWarnings(
    felm(y ~ x1 + x2 | 0 | 0 | firm + year, data = d, psdef = psdef)
  )
  co <- suppressWarnings(summary(fit)$coefficients)

  q <- list()
  for (term in c("x1", "x2")) {
    q[[paste0("coef@", term)]] <- co[term, 1]
    q[[paste0("se@", term)]] <- co[term, 2]
    q[[paste0("t@", term)]] <- co[term, 3]
  }

  # The eigenvalues are the mechanism, not a side quantity. The smallest one is
  # negative before the adjustment and zero after, and that single number is the
  # whole explanation for why a standard error moved by a factor of six.
  ev <- sort(eigen(fit$clustervcv, only.values = TRUE)$values)
  q[["min_eigenvalue@clustervcv"]] <- ev[[1]]

  list(
    quantities = q,
    diagnostics = list(
      lfe_version = as.character(packageVersion("lfe")),
      psdef = psdef,
      n = nrow(d),
      firms = nlevels(d$firm),
      years = nlevels(d$year)
    )
  )
}

backend <- if (psdef) "adjusted" else "unadjusted"
cc_main("lfe_multiway_psdef", backend, body, packages = c("lfe"))
