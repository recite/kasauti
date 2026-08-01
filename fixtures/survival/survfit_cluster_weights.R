# survival@3.6-1#8 -- case weights varying between rows in the same cluster.
#
# "case weights varying between rows in the same cluster"
#
# The fixture is built in counting-process form with two rows per subject and a
# weight that differs between them, so the condition is a property of the data
# rather than something the script has to arrange. The control checks it held.

source(file.path(Sys.getenv("MILAAN_LIB", file.path("..", "..", "lib")), "milaan.R"))

cc_pin(cc_args()$flags[[1]])
library(survival)

body <- function(data_path) {
  d <- read.csv(data_path)
  fit <- survival::survfit(
    survival::Surv(start, stop, event) ~ 1,
    data = d,
    weights = d$w,
    id = d$id,
    cluster = d$cl,
    robust = TRUE
  )

  # Whether the curve itself moved, and whether its standard error did, are
  # different claims, so both travel.
  list(
    quantities = c(
      cc_flatten(fit$surv, "surv"),
      cc_flatten(fit$std.err, "std.err"),
      cc_flatten(fit$n.event, "n.event")
    ),
    diagnostics = list(
      control = any(tapply(d$w, d$cl, function(x) length(unique(x)) > 1L)),
      control_says = "at least one cluster contains rows with different case weights"
    )
  )
}

cc_main("survival@3.6-1#8", "screen", body, packages = c("survival"))
