#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("usage: candidate_runner.R INPUT.rds OUTPUT.rds")

normalization_source <- "/testbed/R/calcNormFactors.R"
implementation <- "/testbed/R/voomFit.R"
if (!file.exists(normalization_source)) stop("edgeR normalization source is missing")
if (!file.exists(implementation)) stop("R/voomFit.R is missing")

candidate_env <- new.env(parent = globalenv())
sys.source(normalization_source, envir = candidate_env, keep.source = FALSE)
sys.source(implementation, envir = candidate_env, keep.source = FALSE)
if (!exists("voomFit", envir = candidate_env, inherits = FALSE) ||
    !is.function(candidate_env$voomFit)) {
  stop("voomFit is not defined")
}

cases <- readRDS(args[[1L]])
outputs <- lapply(cases, function(case) {
  call_args <- case[c("counts", "design", "contrast", "lib.size", "span", "norm.method")]
  tryCatch(
    list(ok = TRUE, value = do.call(candidate_env$voomFit, call_args)),
    error = function(error) list(ok = FALSE, error = conditionMessage(error))
  )
})
saveRDS(outputs, args[[2L]], version = 3L)
