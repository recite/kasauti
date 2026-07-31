# Extract function-call sites from R scripts using R's own parser.
#
# Invoked as: Rscript extract_r.R <file-list.txt> <out.csv>
#
# Regex over source text cannot tell a call from a string, a comment, or a
# variable that happens to share a name. R's parser can: getParseData tags every
# token, and SYMBOL_FUNCTION_CALL is exactly the set of names appearing in call
# position. Namespaced calls (sandwich::vcovHC) surface as SYMBOL_PACKAGE
# followed by the function symbol, so the qualifier is recoverable too.
#
# Scripts that fail to parse are reported rather than dropped. In a corpus of
# published replication archives the parse-failure rate is itself a result.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("usage: Rscript extract_r.R <file-list.txt> <out.csv>")
files <- readLines(args[[1]], warn = FALSE)
files <- files[nzchar(files)]

con <- file(args[[2]], open = "wt")
writeLines("file,fname,qualifier,n", con)

failures <- 0L
for (path in files) {
  parsed <- tryCatch(
    parse(path, keep.source = TRUE),
    error = function(e) NULL,
    warning = function(w) NULL
  )
  if (is.null(parsed)) {
    failures <- failures + 1L
    next
  }

  pd <- tryCatch(utils::getParseData(parsed), error = function(e) NULL)
  if (is.null(pd) || !nrow(pd)) next

  calls <- pd[pd$token == "SYMBOL_FUNCTION_CALL", , drop = FALSE]
  if (!nrow(calls)) next

  # A pkg::fn call emits SYMBOL_PACKAGE immediately before the function symbol.
  pkgs <- pd[pd$token == "SYMBOL_PACKAGE", , drop = FALSE]
  qualifier <- vapply(seq_len(nrow(calls)), function(i) {
    prior <- pkgs[pkgs$line1 == calls$line1[i] & pkgs$col1 < calls$col1[i], , drop = FALSE]
    if (!nrow(prior)) "" else prior$text[which.max(prior$col1)]
  }, character(1))

  tab <- aggregate(
    list(n = rep(1L, nrow(calls))),
    by = list(fname = calls$text, qualifier = qualifier),
    FUN = sum
  )
  for (i in seq_len(nrow(tab))) {
    writeLines(
      sprintf('"%s","%s","%s",%d', path, tab$fname[i], tab$qualifier[i], tab$n[i]),
      con
    )
  }
}

close(con)
cat(sprintf("parsed %d files, %d failed to parse\n", length(files), failures))
