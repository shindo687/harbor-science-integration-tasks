marker_table <- function(genes) {
  n <- length(genes)
  data.frame(
    p_val = seq_len(n) / (1000 + n),
    avg_log2FC = seq(0.25, 2.5, length.out = n),
    pct.1 = seq(0.55, 0.95, length.out = n),
    pct.2 = seq(0.05, 0.35, length.out = n),
    p_val_adj = seq_len(n) / (100 + n),
    row.names = genes,
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
}

make_annotation_case <- function(
    name,
    n_genes = 200L,
    n_markers = 15L,
    sizes = c(10L, 16L, 22L, 28L, 35L, 42L, 50L, 60L, 72L, 84L, 96L, 110L),
    hits = c(8L, 7L, 6L, 5L, 5L, 4L, 4L, 3L, 3L, 2L, 2L, 1L),
    marker_mode = "character",
    include_all = TRUE) {
  all_genes <- sprintf("g%04d", seq_len(n_genes))
  query <- all_genes[seq_len(n_markers)]
  background <- setdiff(all_genes, query)
  stopifnot(length(sizes) == length(hits), all(sizes >= hits), all(hits <= n_markers))

  sets <- vector("list", length(sizes))
  names(sets) <- sprintf("TERM_%02d", seq_along(sizes))
  for (i in seq_along(sets)) {
    need <- sizes[[i]] - hits[[i]]
    selected_background <- character()
    if (need > 0L) {
      start <- ((i - 1L) * 17L) %% length(background)
      index <- ((start + seq_len(need) - 1L) %% length(background)) + 1L
      selected_background <- background[index]
    }
    sets[[i]] <- unique(c(query[seq_len(hits[[i]])], selected_background))
  }
  if (include_all) {
    sets[["TERM_ALL"]] <- all_genes
  }

  term2gene <- data.frame(
    term = rep(names(sets), lengths(sets)),
    gene = unlist(sets, use.names = FALSE),
    stringsAsFactors = FALSE
  )
  term2name <- data.frame(
    term = names(sets),
    name = paste("Pathway", names(sets)),
    stringsAsFactors = FALSE
  )
  markers <- if (identical(marker_mode, "table")) marker_table(query) else query
  list(
    name = name,
    markers = markers,
    TERM2GENE = term2gene,
    universe = NULL,
    TERM2NAME = term2name,
    minGSSize = 1L,
    maxGSSize = 500L,
    pvalueCutoff = 1,
    qvalueCutoff = 1
  )
}

public_cases <- function() {
  one <- make_annotation_case("public-marker-table", marker_mode = "table")

  two <- make_annotation_case("public-duplicates")
  two$markers <- c(two$markers, two$markers[c(1L, 3L, 3L)], "not-annotated")

  three <- make_annotation_case("public-custom-universe", n_genes = 240L, n_markers = 18L)
  three$universe <- sprintf("g%04d", seq_len(170L))

  four <- make_annotation_case("public-size-window")
  four$minGSSize <- 22L
  four$maxGSSize <- 60L

  five <- make_annotation_case("public-empty-hit")
  five$markers <- c("outside-a", "outside-b")

  list(one, two, three, four, five)
}

hidden_cases <- function() {
  cases <- list()
  cases[[1L]] <- make_annotation_case("balanced-overlap")
  cases[[2L]] <- make_annotation_case("seurat-marker-table", marker_mode = "table")

  cases[[3L]] <- make_annotation_case("duplicate-and-unmapped-markers")
  cases[[3L]]$markers <- c(
    cases[[3L]]$markers,
    cases[[3L]]$markers[c(1L, 1L, 5L, 9L)],
    "outside-001", "outside-002"
  )

  cases[[4L]] <- make_annotation_case(
    "small-background",
    n_genes = 80L,
    n_markers = 10L,
    sizes = c(7L, 10L, 14L, 18L, 24L, 30L, 38L, 50L, 62L),
    hits = c(6L, 6L, 5L, 5L, 4L, 3L, 3L, 2L, 1L)
  )

  cases[[5L]] <- make_annotation_case(
    "large-extreme-tail",
    n_genes = 1000L,
    n_markers = 25L,
    sizes = c(18L, 30L, 45L, 70L, 100L, 140L, 190L, 250L, 330L, 420L),
    hits = c(17L, 15L, 13L, 11L, 9L, 7L, 5L, 4L, 3L, 1L)
  )

  cases[[6L]] <- make_annotation_case("intersected-universe", n_genes = 260L, n_markers = 16L)
  cases[[6L]]$universe <- c(sprintf("g%04d", seq_len(180L)), "not-annotated")

  cases[[7L]] <- make_annotation_case("inclusive-minimum-boundary")
  cases[[7L]]$minGSSize <- 22L
  cases[[7L]]$maxGSSize <- 110L

  cases[[8L]] <- make_annotation_case("inclusive-maximum-boundary")
  cases[[8L]]$minGSSize <- 10L
  cases[[8L]]$maxGSSize <- 42L

  cases[[9L]] <- make_annotation_case("pvalue-filter")
  cases[[9L]]$pvalueCutoff <- 0.05

  cases[[10L]] <- make_annotation_case("qvalue-filter", n_genes = 300L, n_markers = 18L)
  cases[[10L]]$qvalueCutoff <- 0.15

  cases[[11L]] <- make_annotation_case("unicode-descriptions")
  cases[[11L]]$TERM2NAME$name <- paste0("通路-", seq_len(nrow(cases[[11L]]$TERM2NAME)))

  cases[[12L]] <- make_annotation_case("duplicate-and-reordered-annotation")
  original <- cases[[12L]]$TERM2GENE
  cases[[12L]]$TERM2GENE <- rbind(
    original[nrow(original):1L, , drop = FALSE],
    original[c(1L, 2L, 2L, 10L), , drop = FALSE],
    data.frame(term = c(NA, "TERM_01"), gene = c("g0001", NA), stringsAsFactors = FALSE)
  )

  cases[[13L]] <- make_annotation_case("no-mapped-query")
  cases[[13L]]$markers <- c("x1", "x2", "x2")

  cases[[14L]] <- make_annotation_case(
    "all-small-p-qvalue-na",
    n_genes = 200L,
    n_markers = 12L,
    sizes = rep(24L, 15L),
    hits = rep(8L, 15L),
    include_all = FALSE
  )

  cases[[15L]] <- make_annotation_case("missing-term-names", n_genes = 220L, n_markers = 14L)
  cases[[15L]]$TERM2NAME <- cases[[15L]]$TERM2NAME[-c(2L, 5L, 9L), , drop = FALSE]
  cases[[15L]]$universe <- sprintf("g%04d", seq_len(175L))

  cases
}

invalid_cases <- function() {
  base <- make_annotation_case("invalid-template")
  list(
    within(base, { name <- "numeric-markers"; markers <- c(1, 2, 3) }),
    within(base, { name <- "non-data-frame-term2gene"; TERM2GENE <- list(a = 1) }),
    within(base, { name <- "one-column-term2gene"; TERM2GENE <- data.frame(term = "x") }),
    within(base, { name <- "numeric-universe"; universe <- c(1, 2, 3) }),
    within(base, { name <- "invalid-size-order"; minGSSize <- 20L; maxGSSize <- 10L }),
    within(base, { name <- "negative-min-size"; minGSSize <- -1L }),
    within(base, { name <- "p-cutoff-above-one"; pvalueCutoff <- 1.1 }),
    within(base, { name <- "q-cutoff-below-zero"; qvalueCutoff <- -0.1 }),
    within(base, { name <- "invalid-term2name"; TERM2NAME <- data.frame(term = "x") })
  )
}

