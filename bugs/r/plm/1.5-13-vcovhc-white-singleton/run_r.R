source(file.path(Sys.getenv("CONCORD_LIB", file.path("..", "..", "..", "lib")), "concord.R"))

flags <- cc_args()$flags
lib <- if (length(flags)) flags[[1]] else ""
if (nzchar(lib)) library(plm, lib.loc = lib) else library(plm)

body <- function(data_path) {
  fit_and_extract <- function(path, tag) {
    d <- read.csv(path)
    m <- plm(y ~ x + z, data = d, index = c("id", "tm"), model = "within")
    out <- list()
    for (meth in c("arellano", "white1", "white2")) {
      # A method that raises is the observation, not a failure of the case:
      # this bug turns out to error rather than return a wrong number, and the
      # only way to record that is to let the try() result through as NA.
      v <- try(plm::vcovHC(m, method = meth), silent = TRUE)
      key <- paste0("se.x@", tag, "_", meth)
      out[[key]] <- if (inherits(v, "try-error")) NA_real_ else sqrt(v[1, 1])
      key <- paste0("se.z@", tag, "_", meth)
      out[[key]] <- if (inherits(v, "try-error")) NA_real_ else sqrt(v[2, 2])
    }
    out
  }

  balanced <- fit_and_extract(data_path, "balanced")
  singleton <- fit_and_extract(
    file.path(dirname(data_path), "singleton.csv"), "singleton"
  )

  list(
    quantities = c(balanced, singleton),
    diagnostics = list(
      plm_version = as.character(
        packageVersion("plm", lib.loc = if (nzchar(lib)) lib else NULL)
      )
    )
  )
}

backend <- if (nzchar(lib)) "buggy" else "fixed"
cc_main("plm_vcovhc_singleton", backend, body, packages = c("plm"))
