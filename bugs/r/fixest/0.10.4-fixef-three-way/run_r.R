source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

flags <- cc_args()$flags
lib <- if (length(flags)) flags[[1]] else ""
if (nzchar(lib)) library(fixest, lib.loc = lib) else library(fixest)

body <- function(data_path) {
  d <- read.csv(data_path)
  for (nm in c("id", "yr", "ind", "reg")) d[[nm]] <- factor(d[[nm]])

  fit <- feols(y ~ x | id + yr + ind + reg, data = d, warn = FALSE, notes = FALSE)
  fe <- fixef(fit)

  # The identity that settles which version is right without an external oracle.
  # Fixed effects are defined by what they reconstruct: sweeping them out and
  # then solving for them has to return values that, added back to Xb, reproduce
  # the fit. A version failing this is wrong on its own terms, so this case does
  # not need a third implementation to adjudicate -- unusual here, and the reason
  # this bug could be settled in one sitting.
  reconstructed <- coef(fit)[["x"]] * d$x +
    fe$id[as.character(d$id)] +
    fe$yr[as.character(d$yr)] +
    fe$ind[as.character(d$ind)] +
    fe$reg[as.character(d$reg)]
  residual <- max(abs(reconstructed - as.numeric(fitted(fit))))

  q <- list(
    "coef@x" = coef(fit)[["x"]],
    "reconstruction_error@fixef" = residual
  )
  # First level of each dimension, to show the values themselves move and not
  # merely their sum. Sorted by name so the mapping is stable across versions.
  for (nm in names(fe)) {
    values <- fe[[nm]]
    q[[paste0("fe@", nm, "_1")]] <- unname(values[order(names(values))][[1]])
  }

  list(
    quantities = q,
    diagnostics = list(
      fixest_version = as.character(
        packageVersion("fixest", lib.loc = if (nzchar(lib)) lib else NULL)
      ),
      n = nrow(d),
      dimensions = length(fe),
      levels = paste(vapply(fe, length, integer(1)), collapse = ",")
    )
  )
}

backend <- if (nzchar(lib)) "buggy" else "fixed"
cc_main("fixest_fixef_multiway", backend, body, packages = c("fixest"))
