source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

# Library path arrives as a flag, so one script serves the buggy and the fixed
# version. Same trick as sandwich-2.5-0-vcovhc-mlm-sign.
flags <- cc_args()$flags
lib <- if (length(flags)) flags[[1]] else ""
if (nzchar(lib)) library(sandwich, lib.loc = lib) else library(sandwich)

body <- function(data_path) {
  d <- read.csv(data_path)
  d$g <- factor(d$g)

  # Three fits off one dataset. The plain lm is the control: the changelog says
  # the bug is confined to glm objects and weighted lm, so if the plain fit
  # moves too, the entry understates its own reach and the case has found
  # something the changelog does not claim.
  fits <- list(
    plain = lm(y ~ x, data = d),
    weighted = lm(y ~ x, data = d, weights = w),
    glm = glm(y ~ x, family = binomial, data = d)
  )

  q <- list()
  for (nm in names(fits)) {
    m <- fits[[nm]]
    for (type in c("HC0", "HC2", "HC3")) {
      v <- try(sandwich::vcovCL(m, cluster = d$g, type = type), silent = TRUE)
      key <- paste0("se.x@", nm, "_", type)
      q[[key]] <- if (inherits(v, "try-error")) NA_real_ else sqrt(v[2, 2])
    }
  }

  list(
    quantities = q,
    diagnostics = list(
      sandwich_version = as.character(
        packageVersion("sandwich", lib.loc = if (nzchar(lib)) lib else NULL)
      ),
      n = nrow(d),
      clusters = nlevels(d$g)
    )
  )
}

backend <- if (nzchar(lib)) "buggy" else "fixed"
cc_main("sandwich_vcovcl_hc2", backend, body, packages = c("sandwich"))
