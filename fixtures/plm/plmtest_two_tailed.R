# plm@1.2-6#4 -- the p-value plmtest() reports.
#
# "two-tailed tests; p-values were divided by 2 instead of multiplied"
#
# The clearest claim in the whole shortlist: a p-value out by a factor of four,
# in a test applied routinely to decide whether a panel needs random effects.
# The Honda variant is the two-sided one, so it is the variant screened.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(plm)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- plm::plm(y ~ x1 + x2, data = d, index = c("id", "year"), model = "pooling")
  test <- plm::plmtest(fit, type = "honda")
  alternative <- tolower(paste(test$alternative, collapse = " "))

  list(
    quantities = list(
      statistic = unname(test$statistic),
      p.value = unname(test$p.value)
    ),
    diagnostics = list(
      # The claim is about two-tailed tests specifically, so a one-sided
      # alternative would mean the fixture screened the wrong branch.
      control = is.finite(test$p.value) &&
        !grepl("greater|less|one[ .-]sided", alternative),
      control_says = paste0(
        "plmtest(type = 'honda') returned a p-value against alternative '",
        alternative, "'"
      )
    )
  )
}

cc_main("plm@1.2-6#4", "screen", body, packages = c("plm"))
