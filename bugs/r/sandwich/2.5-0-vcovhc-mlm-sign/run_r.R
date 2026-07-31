source(file.path(Sys.getenv("KASAUTI_LIB", file.path("..", "..", "..", "lib")), "kasauti.R"))

# The library path is passed as a flag by the case, so the same script serves
# both the buggy and the fixed version. This is the whole archaeology trick: a
# pinned old package is just another backend writing the same result schema.
flags <- cc_args()$flags
lib <- if (length(flags)) flags[[1]] else ""
if (nzchar(lib)) library(sandwich, lib.loc = lib) else library(sandwich)

body <- function(data_path) {
  d <- read.csv(data_path)
  m <- lm(cbind(y1, y2) ~ x, data = d)
  v <- sandwich::vcovHC(m, type = "HC0")

  # Report the two blocks separately, because they behave differently: the
  # within-equation diagonal is unaffected by the bug (the cross product squares
  # the residual, so the lost sign cancels), while the cross-equation block --
  # the one a joint test across equations depends on -- is wrong.
  list(
    quantities = list(
      "vcov.y1_int.y1_int@within" = v[1, 1],
      "vcov.y1_x.y1_x@within" = v[2, 2],
      "vcov.y2_int.y2_int@within" = v[3, 3],
      "vcov.y2_x.y2_x@within" = v[4, 4],
      "vcov.y1_int.y1_x@within" = v[1, 2],
      "vcov.y2_int.y2_x@within" = v[3, 4],
      "vcov.y1_int.y2_int@cross" = v[1, 3],
      "vcov.y1_x.y2_x@cross" = v[2, 4],
      "vcov.y1_int.y2_x@cross" = v[1, 4],
      "vcov.y1_x.y2_int@cross" = v[2, 3]
    ),
    diagnostics = list(
      sandwich_version = as.character(
        packageVersion("sandwich", lib.loc = if (nzchar(lib)) lib else NULL)
      ),
      n = nrow(d),
      responses = 2L
    )
  )
}

backend <- if (nzchar(lib)) "sandwich_2.4-0" else "sandwich_current"
cc_main("sandwich_mlm_sign", backend, body, packages = c("sandwich"))
