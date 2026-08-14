#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, warn = 1)

edge_root <- "/sources/edgeR"
limma_root <- "/sources/limma"
statmod_root <- "/sources/statmod"

edge_env <- new.env(parent = globalenv())
sys.source(file.path(edge_root, "R/calcNormFactors.R"), envir = edge_env)

limma_env <- globalenv()
sys.source(file.path(statmod_root, "R/digamma.R"), envir = limma_env)
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
for (name in limma_files) {
  sys.source(file.path(limma_root, "R", name), envir = limma_env)
}

set.seed(5005L)
genes <- 240L
samples <- 8L
group <- factor(rep(c("control", "treated"), each = samples / 2L))
design <- model.matrix(~ group)
baseline <- exp(seq(log(5), log(700), length.out = genes))
counts <- matrix(
  rpois(genes * samples, lambda = rep(baseline, samples)),
  nrow = genes,
  ncol = samples,
  dimnames = list(sprintf("gene_%04d", seq_len(genes)), sprintf("sample_%02d", seq_len(samples)))
)
counts[1:30, group == "treated"] <- counts[1:30, group == "treated"] +
  rpois(30L * sum(group == "treated"), lambda = rep(baseline[1:30] * 1.5, sum(group == "treated")))

library_sizes <- colSums(counts)
norm_factors <- edge_env$calcNormFactors.default(
  counts,
  lib.size = library_sizes,
  method = "TMM"
)
effective_sizes <- library_sizes * norm_factors

voomed <- limma_env$voom(
  counts,
  design = design,
  lib.size = effective_sizes,
  normalize.method = "none",
  span = 0.5,
  plot = FALSE
)
fit <- limma_env$lmFit(voomed, design)
contrast <- matrix(c(0, 1), ncol = 1L, dimnames = list(colnames(design), "treated-control"))
fit <- limma_env$contrasts.fit(fit, contrasts = contrast)
fit <- limma_env$eBayes(fit, trend = FALSE, robust = FALSE)

cat("edgeR", read.dcf(file.path(edge_root, "DESCRIPTION"), fields = "Version")[[1L]], "\n")
cat("limma", read.dcf(file.path(limma_root, "DESCRIPTION"), fields = "Version")[[1L]], "\n")
cat("norm factor range", format(range(norm_factors), digits = 12L), "\n")
cat("logCPM dimensions", paste(dim(voomed$E), collapse = "x"), "\n")
cat("weight range", format(range(voomed$weights), digits = 12L), "\n")
cat("coefficient head", paste(format(head(fit$coefficients[, 1L]), digits = 12L), collapse = " "), "\n")
cat("moderated t head", paste(format(head(fit$t[, 1L]), digits = 12L), collapse = " "), "\n")
cat("p-value head", paste(format(head(fit$p.value[, 1L]), digits = 12L), collapse = " "), "\n")
