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
    marker_mode = "character") {
  all_genes <- sprintf("g%04d", seq_len(n_genes))
  query <- all_genes[seq_len(n_markers)]
  background <- setdiff(all_genes, query)
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
  sets[["TERM_ALL"]] <- all_genes
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
  list(
    name = name,
    markers = if (identical(marker_mode, "table")) marker_table(query) else query,
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

