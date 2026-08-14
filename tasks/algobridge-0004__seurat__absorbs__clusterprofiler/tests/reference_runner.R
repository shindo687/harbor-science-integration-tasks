#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("usage: reference_runner.R INPUT.rds OUTPUT.rds")
}

input_path <- args[[1L]]
output_path <- args[[2L]]
reference_root <- "/opt/reference"
set.seed(4004L)

required <- c(
  file.path(reference_root, "qvalue/R/pi0est.R"),
  file.path(reference_root, "qvalue/R/lfdr.R"),
  file.path(reference_root, "qvalue/R/qvalue.R"),
  file.path(reference_root, "DOSE/R/00-AllClasses.R"),
  file.path(reference_root, "DOSE/R/build_Anno.R"),
  file.path(reference_root, "DOSE/R/enricher_internal.R"),
  file.path(reference_root, "clusterProfiler/R/enricher.R")
)
if (!all(file.exists(required))) {
  stop("locked reference sources are incomplete")
}

# The locked files are sourced into the process global environment so the S4
# class registered by DOSE has the same non-package development semantics as
# sourcing those files in an upstream checkout.
reference_env <- globalenv()
for (path in required) {
  sys.source(path, envir = reference_env, keep.source = FALSE)
}

empty_result <- function() {
  data.frame(
    term = character(),
    description = character(),
    overlap = integer(),
    GeneRatio = character(),
    BgRatio = character(),
    pvalue = double(),
    p.adjust = double(),
    qvalue = double(),
    genes = character(),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
}

marker_ids <- function(markers) {
  if (is.data.frame(markers)) row.names(markers) else markers
}

canonical_reference <- function(case) {
  result <- reference_env$enricher(
    gene = marker_ids(case$markers),
    pvalueCutoff = case$pvalueCutoff,
    pAdjustMethod = "BH",
    universe = case$universe,
    minGSSize = case$minGSSize,
    maxGSSize = case$maxGSSize,
    qvalueCutoff = case$qvalueCutoff,
    TERM2GENE = case$TERM2GENE,
    TERM2NAME = case$TERM2NAME
  )
  if (is.null(result)) {
    return(empty_result())
  }
  result <- reference_env$get_enriched(result)
  table <- result@result
  if (nrow(table) == 0L) {
    return(empty_result())
  }
  hits <- vapply(
    strsplit(as.character(table$geneID), "/", fixed = TRUE),
    function(x) paste(sort(unique(x), method = "radix"), collapse = "/"),
    character(1L)
  )
  output <- data.frame(
    term = as.character(table$ID),
    description = as.character(table$Description),
    overlap = as.integer(table$Count),
    GeneRatio = as.character(table$GeneRatio),
    BgRatio = as.character(table$BgRatio),
    pvalue = as.double(table$pvalue),
    p.adjust = as.double(table$p.adjust),
    qvalue = as.double(table$qvalue),
    genes = hits,
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
  output <- output[order(output$pvalue, output$term, method = "radix"), , drop = FALSE]
  row.names(output) <- NULL
  output
}

cases <- readRDS(input_path)
outputs <- lapply(cases, function(case) {
  tryCatch(
    list(ok = TRUE, value = canonical_reference(case)),
    error = function(error) list(ok = FALSE, error = conditionMessage(error))
  )
})
saveRDS(outputs, output_path, version = 3L)
