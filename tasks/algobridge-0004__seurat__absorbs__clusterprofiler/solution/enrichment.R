# Native bounded over-representation analysis for Seurat marker results.
EnrichMarkers <- function(
    markers,
    TERM2GENE,
    universe = NULL,
    TERM2NAME = NULL,
    minGSSize = 1L,
    maxGSSize = 500L,
    pvalueCutoff = 1,
    qvalueCutoff = 1) {
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

  scalar_number <- function(x) {
    is.numeric(x) && length(x) == 1L && !is.na(x) && is.finite(x)
  }
  scalar_integer <- function(x) {
    scalar_number(x) && x == floor(x)
  }

  if (is.data.frame(markers)) {
    query <- row.names(markers)
  } else if (is.character(markers)) {
    query <- markers
  } else {
    stop("markers must be a character vector or data.frame")
  }
  if (anyNA(query) || any(!nzchar(query))) {
    stop("marker IDs must be non-missing and non-empty")
  }
  if (!is.data.frame(TERM2GENE) || ncol(TERM2GENE) < 2L) {
    stop("TERM2GENE must be a two-column data.frame")
  }
  if (!is.null(universe) && !is.character(universe)) {
    stop("universe must be NULL or character")
  }
  if (!is.null(TERM2NAME) &&
      (!is.data.frame(TERM2NAME) || ncol(TERM2NAME) < 2L)) {
    stop("TERM2NAME must be NULL or a two-column data.frame")
  }
  if (!scalar_integer(minGSSize) || !scalar_integer(maxGSSize) ||
      minGSSize < 1 || maxGSSize < minGSSize) {
    stop("gene-set size bounds are invalid")
  }
  if (!scalar_number(pvalueCutoff) || pvalueCutoff < 0 || pvalueCutoff > 1 ||
      !scalar_number(qvalueCutoff) || qvalueCutoff < 0 || qvalueCutoff > 1) {
    stop("cutoffs must be finite numbers in [0, 1]")
  }

  query <- unique(as.character(query))
  pairs <- data.frame(
    term = as.character(TERM2GENE[[1L]]),
    gene = as.character(TERM2GENE[[2L]]),
    stringsAsFactors = FALSE
  )
  pairs <- pairs[!is.na(pairs$term) & !is.na(pairs$gene), , drop = FALSE]
  pairs <- pairs[nzchar(pairs$term) & nzchar(pairs$gene), , drop = FALSE]
  pairs <- unique(pairs)
  if (nrow(pairs) == 0L || length(query) == 0L) {
    return(empty_result())
  }

  annotated <- unique(pairs$gene)
  background <- if (is.null(universe)) {
    annotated
  } else {
    intersect(annotated, unique(universe))
  }
  if (length(background) == 0L) {
    return(empty_result())
  }

  mapped_query <- query[query %in% annotated]
  if (length(mapped_query) == 0L) {
    return(empty_result())
  }
  query_pairs <- pairs[pairs$gene %in% mapped_query, , drop = FALSE]
  hit_terms <- sort(unique(query_pairs$term), method = "radix")
  term_sets <- split(pairs$gene[pairs$term %in% hit_terms],
                     pairs$term[pairs$term %in% hit_terms])
  term_sets <- lapply(term_sets, function(x) intersect(unique(x), background))
  keep_size <- lengths(term_sets) >= minGSSize & lengths(term_sets) <= maxGSSize
  term_sets <- term_sets[keep_size]
  if (length(term_sets) == 0L) {
    return(empty_result())
  }

  terms <- names(term_sets)
  hits <- lapply(term_sets, function(x) intersect(mapped_query, x))
  k <- lengths(hits)
  M <- lengths(term_sets)
  N <- length(background)
  n <- length(mapped_query)
  p <- vapply(
    seq_along(terms),
    function(i) phyper(k[[i]] - 1, M[[i]], N - M[[i]], n, lower.tail = FALSE),
    double(1L)
  )
  adjusted <- p.adjust(p, method = "BH")

  pi_zero <- min(1, mean(p >= 0.05) / 0.95)
  if (!is.finite(pi_zero) || pi_zero <= 0) {
    q <- rep(NA_real_, length(p))
  } else {
    count <- length(p)
    decreasing_order <- order(p, decreasing = TRUE)
    reverse_order <- order(decreasing_order)
    reverse_rank <- count:1L
    q <- pi_zero * pmin(
      1,
      cummin(p[decreasing_order] * count / reverse_rank)
    )[reverse_order]
  }

  descriptions <- terms
  if (!is.null(TERM2NAME)) {
    names_table <- data.frame(
      term = as.character(TERM2NAME[[1L]]),
      name = as.character(TERM2NAME[[2L]]),
      stringsAsFactors = FALSE
    )
    names_table <- names_table[
      !is.na(names_table$term) & !is.na(names_table$name) &
        nzchar(names_table$term) & nzchar(names_table$name),
      ,
      drop = FALSE
    ]
    names_table <- names_table[!duplicated(names_table$term), , drop = FALSE]
    index <- match(terms, names_table$term)
    found <- !is.na(index)
    descriptions[found] <- names_table$name[index[found]]
  }

  output <- data.frame(
    term = terms,
    description = descriptions,
    overlap = as.integer(k),
    GeneRatio = sprintf("%s/%s", k, n),
    BgRatio = sprintf("%s/%s", M, N),
    pvalue = as.double(p),
    p.adjust = as.double(adjusted),
    qvalue = as.double(q),
    genes = vapply(
      hits,
      function(x) paste(sort(unique(x), method = "radix"), collapse = "/"),
      character(1L)
    ),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )

  selected <- output$pvalue <= pvalueCutoff & output$p.adjust <= pvalueCutoff
  if (!anyNA(output$qvalue)) {
    selected <- selected & output$qvalue <= qvalueCutoff
  }
  output <- output[selected, , drop = FALSE]
  output <- output[order(output$pvalue, output$term, method = "radix"), , drop = FALSE]
  row.names(output) <- NULL
  output
}

