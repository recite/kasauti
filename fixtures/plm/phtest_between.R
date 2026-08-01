# plm@1.5-9#3 -- phtest() on the between model.
#
# "method='aux' with NA values, or the between model (wrong degrees of freedom)"
#
# Degrees of freedom are the claim, so they are reported beside the statistic:
# if only `parameter` moves and the statistic does not, that is the entry
# reproduced exactly rather than a fit that happened to differ.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(plm)

body <- function(data_path) {
  d <- read.csv(data_path)
  index <- c("id", "year")

  within <- plm::plm(y ~ x1 + x2, data = d, index = index, model = "within")
  between <- plm::plm(y ~ x1 + x2, data = d, index = index, model = "between")

  report <- function(test, prefix) {
    stats::setNames(
      list(unname(test$statistic), unname(test$parameter), unname(test$p.value)),
      paste0(prefix, c(".statistic", ".parameter", ".p.value"))
    )
  }

  # Both branches the entry names, in one screen: the between comparison whose
  # degrees of freedom it calls wrong, and the auxiliary-regression method it
  # names explicitly.
  pair <- plm::phtest(within, between)
  # `do.call` with the panel already built, because phtest's formula method
  # resolves `data` in the caller's frame and cannot see a local named `d`.
  aux <- do.call(
    plm::phtest,
    list(y ~ x1 + x2, data = plm::pdata.frame(d, index = index), method = "aux")
  )

  list(
    quantities = c(report(pair, "between"), report(aux, "aux")),
    diagnostics = list(
      control = is.finite(pair$parameter) &&
        is.finite(aux$parameter) &&
        length(coef(between)) == 3L,
      control_says = "phtest() ran against a between fit and via method = 'aux', both reporting degrees of freedom"
    )
  )
}

cc_main("plm@1.5-9#3", "screen", body, packages = c("plm"))
