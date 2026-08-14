#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, warn = 1)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("usage: reference_runner.R INPUT.rds OUTPUT.rds")
}

edge_root <- "/opt/pristine-host"
limma_root <- "/opt/reference/limma"
statmod_root <- "/opt/reference/statmod"

required <- c(
  file.path(edge_root, "DESCRIPTION"),
  file.path(edge_root, "R/calcNormFactors.R"),
  file.path(limma_root, "DESCRIPTION"),
  file.path(statmod_root, "R/digamma.R")
)

limma_files <- c(
  "classes.R",
  "utility.R",
  "norm.R",
  "weights.R",
  "dups.R",
  "lmfit.R",
  "voom.R",
  "contrasts.R",
  "fitFDist.R",
  "fitFDistRobustly.R",
  "fitGammaIntercept.R",
  "fitFDistUnequalDF1.R",
  "squeezeVar.R",
  "decidetests.R",
  "ebayes.R"
)
required <- c(required, file.path(limma_root, "R", limma_files))
if (!all(file.exists(required))) stop("locked reference sources are incomplete")

edge_env <- new.env(parent = globalenv())
sys.source(file.path(edge_root, "R/calcNormFactors.R"), envir = edge_env, keep.source = FALSE)

# S4 classes created by limma's unchanged classes.R need a real top-level
# environment when the locked package sources are evaluated without installing
# the package. All numerical entry points below are the unchanged locked files.
limma_env <- globalenv()
sys.source(file.path(statmod_root, "R/digamma.R"), envir = limma_env, keep.source = FALSE)
for (name in limma_files) {
  sys.source(file.path(limma_root, "R", name), envir = limma_env, keep.source = FALSE)
}

canonical_reference <- function(case) {
  counts <- case$counts
  design <- case$design
  library_sizes <- case$lib.size
  if (is.null(library_sizes)) library_sizes <- colSums(counts)

  norm_factors <- edge_env$calcNormFactors.default(
    counts,
    lib.size = library_sizes,
    method = case$norm.method
  )
  effective_sizes <- library_sizes * norm_factors

  voomed <- limma_env$voom(
    counts,
    design = design,
    lib.size = effective_sizes,
    normalize.method = "none",
    span = case$span,
    plot = FALSE
  )
  base_fit <- limma_env$lmFit(voomed, design)
  contrast_matrix <- matrix(
    case$contrast,
    ncol = 1L,
    dimnames = list(colnames(design), "contrast")
  )
  contrast_fit <- limma_env$contrasts.fit(base_fit, contrasts = contrast_matrix)
  contrast_fit <- limma_env$eBayes(contrast_fit, trend = FALSE, robust = FALSE)

  list(
    logCPM = unname(as.matrix(voomed$E)),
    weights = unname(as.matrix(voomed$weights)),
    coefficients = unname(as.matrix(base_fit$coefficients)),
    contrast.coefficients = unname(as.double(contrast_fit$coefficients[, 1L])),
    t = unname(as.double(contrast_fit$t[, 1L])),
    p.value = unname(as.double(contrast_fit$p.value[, 1L])),
    df.total = unname(as.double(contrast_fit$df.total)),
    norm.factors = unname(as.double(norm_factors))
  )
}

cases <- readRDS(args[[1L]])
outputs <- lapply(cases, function(case) {
  tryCatch(
    list(ok = TRUE, value = canonical_reference(case)),
    error = function(error) list(ok = FALSE, error = conditionMessage(error))
  )
})
saveRDS(outputs, args[[2L]], version = 3L)
