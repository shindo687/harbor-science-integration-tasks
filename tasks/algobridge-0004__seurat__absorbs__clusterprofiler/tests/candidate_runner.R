#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("usage: candidate_runner.R INPUT.rds OUTPUT.rds")
}

implementation <- "/testbed/R/enrichment.R"
if (!file.exists(implementation)) {
  stop("R/enrichment.R is missing")
}

candidate_env <- new.env(parent = globalenv())
sys.source(implementation, envir = candidate_env, keep.source = FALSE)
if (!exists("EnrichMarkers", envir = candidate_env, inherits = FALSE) ||
    !is.function(candidate_env$EnrichMarkers)) {
  stop("EnrichMarkers is not defined")
}

cases <- readRDS(args[[1L]])
outputs <- lapply(cases, function(case) {
  call_args <- case[c(
    "markers", "TERM2GENE", "universe", "TERM2NAME", "minGSSize",
    "maxGSSize", "pvalueCutoff", "qvalueCutoff"
  )]
  tryCatch(
    list(ok = TRUE, value = do.call(candidate_env$EnrichMarkers, call_args)),
    error = function(error) list(ok = FALSE, error = conditionMessage(error))
  )
})
saveRDS(outputs, args[[2L]], version = 3L)

