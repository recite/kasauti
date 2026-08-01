# plm@1.2-8#2 -- vcovBK() when a matrix degenerates into a vector.
#
# "matrices degenerating into vectors"
#
# R drops a dimension whenever a subscript leaves one row or column, which is
# the whole class of defect here. A single regressor is the smallest way to
# reach it, so the screen fits one alongside the multi-regressor case and reports
# both: if only the one-column fit moves, the entry is exactly what it says.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(plm)

body <- function(data_path) {
  d <- read.csv(data_path)
  index <- c("id", "year")

  narrow <- plm::plm(y ~ x1, data = d, index = index, model = "pooling")
  wide <- plm::plm(y ~ x1 + x2, data = d, index = index, model = "pooling")

  list(
    quantities = c(
      cc_flatten(plm::vcovBK(narrow), "narrow"),
      cc_flatten(plm::vcovBK(wide), "wide")
    ),
    diagnostics = list(
      control = length(coef(narrow)) == 2L && length(coef(wide)) == 3L,
      control_says = "vcovBK() on a one-regressor fit, where R drops the dimension, beside a two-regressor fit"
    )
  )
}

cc_main("plm@1.2-8#2", "screen", body, packages = c("plm"))
