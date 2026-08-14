#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("usage: verify_examples.R ACTUAL.rds EXPECTED.rds")

actual <- readRDS(args[[1L]])
expected <- readRDS(args[[2L]])
if (length(actual) != length(expected)) stop("case count mismatch")

tolerances <- list(
  logCPM = c(abs = 5e-10, rel = 5e-10),
  weights = c(abs = 2e-7, rel = 5e-8),
  coefficients = c(abs = 2e-8, rel = 2e-8),
  contrast.coefficients = c(abs = 2e-8, rel = 2e-8),
  t = c(abs = 2e-6, rel = 2e-7),
  p.value = c(abs = 2e-8, rel = 2e-6),
  df.total = c(abs = 2e-8, rel = 2e-8),
  norm.factors = c(abs = 5e-10, rel = 5e-10)
)

close_numeric <- function(x, y, tolerance) {
  identical(dim(x), dim(y)) &&
    identical(length(x), length(y)) &&
    identical(is.na(x), is.na(y)) &&
    all(abs(x - y) <= tolerance[["abs"]] + tolerance[["rel"]] * pmax(abs(y), .Machine$double.xmin))
}

passed <- logical(length(expected))
for (i in seq_along(expected)) {
  if (!isTRUE(actual[[i]]$ok) || !isTRUE(expected[[i]]$ok)) next
  av <- actual[[i]]$value
  ev <- expected[[i]]$value
  if (!identical(names(av), names(tolerances))) next
  passed[[i]] <- all(vapply(
    names(tolerances),
    function(name) close_numeric(av[[name]], ev[[name]], tolerances[[name]]),
    logical(1L)
  ))
}

cat(sprintf("public examples: %d/%d passed\n", sum(passed), length(passed)))
if (!all(passed)) quit(save = "no", status = 1L)
