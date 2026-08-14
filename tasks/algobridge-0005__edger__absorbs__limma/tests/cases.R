make_case <- function(
    name,
    seed,
    design,
    contrast,
    n_genes = 160L,
    depth = rep(1, nrow(design)),
    signal = rep(0, nrow(design)),
    effect_fraction = 0.18,
    effect_size = 0.8,
    dispersion_size = 18,
    norm.method = "TMM",
    span = 0.5,
    explicit_lib_size = NULL,
    zero_fraction = 0) {
  stopifnot(
    is.matrix(design),
    nrow(design) == length(depth),
    length(depth) == length(signal),
    length(contrast) == ncol(design),
    n_genes >= 40L,
    all(depth > 0),
    span > 0,
    span <= 1
  )
  set.seed(as.integer(seed))
  baseline <- exp(seq(log(3), log(900), length.out = n_genes))
  baseline <- baseline * exp(rnorm(n_genes, sd = 0.22))
  mean_matrix <- outer(baseline, depth)
  affected <- seq_len(max(3L, floor(n_genes * effect_fraction)))
  if (length(affected)) {
    gene_effect <- effect_size * seq(0.65, 1.25, length.out = length(affected))
    mean_matrix[affected, ] <- mean_matrix[affected, , drop = FALSE] *
      exp(outer(gene_effect, signal))
  }
  counts <- matrix(
    rnbinom(length(mean_matrix), mu = as.vector(mean_matrix), size = dispersion_size),
    nrow = n_genes,
    ncol = nrow(design)
  )
  if (zero_fraction > 0) {
    zero_count <- min(n_genes - 2L, floor(n_genes * zero_fraction))
    if (zero_count > 0L) counts[seq.int(n_genes - zero_count + 1L, n_genes), ] <- 0
  }
  storage.mode(counts) <- "double"
  rownames(counts) <- sprintf("gene_%04d", seq_len(n_genes))
  colnames(counts) <- sprintf("sample_%02d", seq_len(ncol(counts)))
  rownames(design) <- colnames(counts)
  if (is.null(colnames(design))) colnames(design) <- sprintf("coef_%02d", seq_len(ncol(design)))
  contrast <- as.double(contrast)
  names(contrast) <- colnames(design)
  list(
    name = name,
    counts = counts,
    lib.size = if (is.null(explicit_lib_size)) NULL else as.double(explicit_lib_size),
    design = design,
    contrast = contrast,
    span = as.double(span),
    norm.method = norm.method
  )
}

two_group_design <- function(n_control, n_treated) {
  group <- factor(c(rep("control", n_control), rep("treated", n_treated)))
  model.matrix(~ group)
}

three_group_design <- function(per_group) {
  group <- factor(rep(c("A", "B", "C"), each = per_group))
  model.matrix(~ 0 + group)
}

public_cases <- function() {
  d1 <- two_group_design(3L, 3L)
  d2 <- two_group_design(4L, 4L)
  d3 <- two_group_design(3L, 3L)
  x <- seq(-1.5, 1.5, length.out = 7L)
  d4 <- cbind(intercept = 1, slope = x)
  d5 <- three_group_design(3L)
  list(
    make_case(
      "public-balanced-tmm", 500501L, d1, c(0, 1),
      n_genes = 96L, signal = c(rep(0, 3L), rep(1, 3L))
    ),
    make_case(
      "public-depth-and-composition", 500502L, d2, c(0, 1),
      n_genes = 132L,
      depth = c(0.55, 0.8, 1.15, 1.8, 0.65, 0.95, 1.35, 2.1),
      signal = c(rep(0, 4L), rep(1, 4L)),
      effect_fraction = 0.3,
      effect_size = 1.05
    ),
    make_case(
      "public-no-normalization", 500503L, d3, c(0, 1),
      n_genes = 110L,
      depth = c(0.7, 1.0, 1.5, 0.8, 1.2, 1.75),
      signal = c(rep(0, 3L), rep(1, 3L)),
      norm.method = "none"
    ),
    make_case(
      "public-continuous-covariate", 500504L, d4, c(0, 1),
      n_genes = 148L,
      depth = seq(0.75, 1.45, length.out = 7L),
      signal = x,
      span = 0.4,
      effect_size = 0.45
    ),
    make_case(
      "public-three-group-rle", 500505L, d5, c(-1, 0, 1),
      n_genes = 176L,
      depth = rep(c(0.8, 1.0, 1.3), 3L),
      signal = rep(c(0, 0.35, 1), each = 3L),
      norm.method = "RLE",
      span = 0.65
    )
  )
}

hidden_cases <- function() {
  result <- list()

  d <- two_group_design(3L, 3L)
  result[[1L]] <- make_case(
    "balanced-two-group", 500511L, d, c(0, 1),
    n_genes = 120L, signal = c(rep(0, 3L), rep(1, 3L))
  )

  d <- two_group_design(4L, 4L)
  result[[2L]] <- make_case(
    "unequal-library-depths", 500512L, d, c(0, 1),
    n_genes = 165L,
    depth = c(0.35, 0.6, 1.1, 2.4, 0.48, 0.9, 1.55, 2.8),
    signal = c(rep(0, 4L), rep(1, 4L))
  )

  d <- two_group_design(4L, 4L)
  result[[3L]] <- make_case(
    "composition-biased-tmm", 500513L, d, c(0, 1),
    n_genes = 210L,
    depth = c(0.8, 1.0, 1.15, 1.4, 0.75, 0.95, 1.25, 1.5),
    signal = c(rep(0, 4L), rep(1, 4L)),
    effect_fraction = 0.42,
    effect_size = 1.35
  )

  d <- two_group_design(3L, 3L)
  temp <- make_case(
    "explicit-library-sizes", 500514L, d, c(0, 1),
    n_genes = 135L,
    depth = c(0.65, 0.9, 1.35, 0.75, 1.1, 1.6),
    signal = c(rep(0, 3L), rep(1, 3L))
  )
  temp$lib.size <- colSums(temp$counts) + c(700, 1300, 2500, 900, 1800, 3200)
  result[[4L]] <- temp

  d <- two_group_design(3L, 4L)
  result[[5L]] <- make_case(
    "normalization-none", 500515L, d, c(0, 1),
    n_genes = 144L,
    depth = c(0.4, 0.75, 1.6, 0.55, 0.9, 1.35, 2.2),
    signal = c(rep(0, 3L), rep(1, 4L)),
    norm.method = "none"
  )

  d <- two_group_design(4L, 4L)
  result[[6L]] <- make_case(
    "rle-normalization", 500516L, d, c(0, 1),
    n_genes = 190L,
    depth = c(0.6, 0.85, 1.2, 1.7, 0.72, 1.0, 1.4, 2.0),
    signal = c(rep(0, 4L), rep(1, 4L)),
    norm.method = "RLE"
  )

  d <- two_group_design(4L, 4L)
  result[[7L]] <- make_case(
    "upper-quartile-normalization", 500517L, d, c(0, 1),
    n_genes = 185L,
    depth = c(0.5, 0.9, 1.25, 1.9, 0.65, 1.05, 1.5, 2.25),
    signal = c(rep(0, 4L), rep(1, 4L)),
    norm.method = "upperquartile"
  )

  d <- two_group_design(3L, 3L)
  result[[8L]] <- make_case(
    "narrow-lowess-span", 500518L, d, c(0, 1),
    n_genes = 230L,
    signal = c(rep(0, 3L), rep(1, 3L)),
    span = 0.3
  )

  d <- two_group_design(4L, 4L)
  result[[9L]] <- make_case(
    "wide-lowess-span", 500519L, d, c(0, 1),
    n_genes = 155L,
    signal = c(rep(0, 4L), rep(1, 4L)),
    span = 0.8
  )

  x <- c(-1.7, -1.1, -0.4, 0.2, 0.75, 1.3, 1.9)
  d <- cbind(intercept = 1, slope = x)
  result[[10L]] <- make_case(
    "continuous-design", 500520L, d, c(0, 1),
    n_genes = 172L,
    depth = c(0.7, 0.9, 1.05, 1.25, 1.45, 1.15, 0.85),
    signal = x,
    effect_size = 0.38
  )

  d <- three_group_design(3L)
  result[[11L]] <- make_case(
    "three-group-contrast", 500521L, d, c(-1, 0, 1),
    n_genes = 205L,
    depth = rep(c(0.72, 1.0, 1.45), 3L),
    signal = rep(c(0, 0.4, 1), each = 3L),
    span = 0.55
  )

  group <- factor(rep(c("control", "treated"), each = 4L))
  batch <- factor(rep(c("b1", "b2"), 4L))
  d <- model.matrix(~ batch + group)
  result[[12L]] <- make_case(
    "batch-adjusted-design", 500522L, d, c(0, 0, 1),
    n_genes = 198L,
    depth = c(0.75, 1.1, 0.9, 1.35, 0.8, 1.2, 1.0, 1.5),
    signal = as.numeric(group == "treated"),
    effect_size = 0.7
  )

  d <- two_group_design(4L, 4L)
  result[[13L]] <- make_case(
    "sparse-with-all-zero-genes", 500523L, d, c(0, 1),
    n_genes = 180L,
    depth = c(0.5, 0.75, 1.0, 1.4, 0.6, 0.9, 1.2, 1.65),
    signal = c(rep(0, 4L), rep(1, 4L)),
    dispersion_size = 8,
    zero_fraction = 0.12
  )

  d <- two_group_design(3L, 3L)
  result[[14L]] <- make_case(
    "large-gene-panel", 500524L, d, c(0, 1),
    n_genes = 640L,
    signal = c(rep(0, 3L), rep(1, 3L)),
    effect_fraction = 0.08,
    effect_size = 0.95,
    span = 0.45
  )

  d <- two_group_design(3L, 4L)
  result[[15L]] <- make_case(
    "unbalanced-replicates", 500525L, d, c(0, 1),
    n_genes = 128L,
    depth = c(0.55, 1.0, 1.7, 0.65, 0.9, 1.3, 1.9),
    signal = c(rep(0, 3L), rep(1, 4L)),
    norm.method = "RLE",
    span = 0.6
  )
  rownames(result[[15L]]$counts) <- sprintf("RNA-%03d/alpha", seq_len(nrow(result[[15L]]$counts)))
  colnames(result[[15L]]$counts) <- paste0("sample ", LETTERS[seq_len(ncol(result[[15L]]$counts))])
  rownames(result[[15L]]$design) <- colnames(result[[15L]]$counts)

  result
}

invalid_cases <- function() {
  base <- public_cases()[[1L]]
  list(
    within(base, { name <- "negative-count"; counts[1L, 1L] <- -1 }),
    within(base, { name <- "noninteger-count"; counts[1L, 1L] <- 1.25 }),
    within(base, { name <- "count-na"; counts[1L, 1L] <- NA_real_ }),
    within(base, { name <- "design-row-mismatch"; design <- design[-1L, , drop = FALSE] }),
    within(base, { name <- "contrast-length-mismatch"; contrast <- contrast[1L] }),
    within(base, { name <- "rank-deficient-design"; design <- cbind(design, design[, 1L]) }),
    within(base, { name <- "invalid-span"; span <- 1.2 }),
    within(base, { name <- "invalid-normalization"; norm.method <- "quantile" }),
    within(base, { name <- "short-library-size"; lib.size <- c(100, 200) }),
    within(base, { name <- "nonpositive-library-size"; lib.size <- rep(0, ncol(counts)) })
  )
}
