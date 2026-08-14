.vf_check_inputs <- function(counts, design, contrast, lib.size, span, norm.method) {
  if (!is.matrix(counts) || !is.numeric(counts) || length(counts) == 0L) {
    stop("counts must be a non-empty numeric matrix")
  }
  if (nrow(counts) < 3L || ncol(counts) < 3L || any(!is.finite(counts)) ||
      any(counts < 0) || any(counts != round(counts))) {
    stop("counts must contain finite non-negative integer values")
  }
  if (!is.matrix(design) || !is.numeric(design) || any(!is.finite(design)) ||
      nrow(design) != ncol(counts) || ncol(design) < 1L) {
    stop("design is not a compatible finite numeric matrix")
  }
  if (qr(design)$rank != ncol(design) || nrow(design) <= ncol(design)) {
    stop("design must be full rank with residual degrees of freedom")
  }
  if (!is.numeric(contrast) || length(contrast) != ncol(design) ||
      any(!is.finite(contrast)) || all(contrast == 0)) {
    stop("contrast must be a finite nonzero vector matching the design")
  }
  if (length(span) != 1L || !is.numeric(span) || !is.finite(span) ||
      span <= 0 || span > 1) {
    stop("span must be a finite scalar in (0, 1]")
  }
  allowed <- c("TMM", "RLE", "upperquartile", "none")
  if (length(norm.method) != 1L || !is.character(norm.method) ||
      !(norm.method %in% allowed)) {
    stop("unsupported normalization method")
  }
  if (!is.null(lib.size)) {
    if (!is.numeric(lib.size) || length(lib.size) != ncol(counts) ||
        any(!is.finite(lib.size)) || any(lib.size <= 0)) {
      stop("lib.size must contain one positive finite value per sample")
    }
  }
  invisible(TRUE)
}

.vf_log_minus_digamma <- function(value) {
  result <- rep_len(NA_real_, length(value))
  valid <- is.finite(value) & value > 0
  if (!any(valid)) return(result)
  for (index in which(valid)) {
    x <- value[[index]]
    accumulated <- 0
    while (x < 8) {
      accumulated <- accumulated + log(x / (x + 1)) + 1 / x
      x <- x + 1
    }
    inverse_square <- 1 / (x * x)
    coefficients <- c(
      1 / 12,
      -1 / 120,
      1 / 252,
      -1 / 240,
      1 / 132,
      -691 / 32760,
      1 / 12,
      -3617 / 8160
    )
    power <- inverse_square
    correction <- 1 / (2 * x)
    for (coefficient in coefficients) {
      correction <- correction + coefficient * power
      power <- power * inverse_square
    }
    result[[index]] <- accumulated + correction
  }
  result
}

.vf_inverse_trigamma <- function(target) {
  if (!is.numeric(target)) stop("invalid trigamma target")
  answer <- target
  missing <- is.na(target)
  negative <- !missing & target < 0
  answer[negative] <- NaN
  huge <- !missing & !negative & target > 1e7
  answer[huge] <- 1 / sqrt(target[huge])
  tiny <- !missing & !negative & !huge & target < 1e-6
  answer[tiny] <- 1 / target[tiny]
  active <- which(!missing & !negative & !huge & !tiny)
  if (length(active)) {
    estimate <- 0.5 + 1 / target[active]
    for (iteration in seq_len(51L)) {
      tri <- trigamma(estimate)
      step <- tri * (1 - tri / target[active]) / psigamma(estimate, deriv = 2)
      estimate <- estimate + step
      if (max(-step / estimate) < 1e-8) break
    }
    answer[active] <- estimate
  }
  answer
}

.vf_variance_prior <- function(variances, residual_df) {
  usable <- is.finite(variances) & variances >= 0 &
    is.finite(residual_df) & residual_df > 1e-15
  if (sum(usable) < 2L) stop("insufficient residual variances")
  x <- variances[usable]
  df <- residual_df[usable]
  center <- median(x)
  if (center == 0) center <- 1
  x <- pmax(x, 1e-5 * center)
  adjusted_log <- log(x) + .vf_log_minus_digamma(df / 2)
  mean_log <- mean(adjusted_log)
  log_variance <- sum((adjusted_log - mean_log)^2) / (length(x) - 1L)
  log_variance <- log_variance - mean(trigamma(df / 2))
  if (log_variance > 0) {
    prior_df <- 2 * .vf_inverse_trigamma(log_variance)
    prior_scale <- exp(mean_log - .vf_log_minus_digamma(prior_df / 2))
  } else {
    prior_df <- Inf
    prior_scale <- mean(x)
  }
  list(scale = prior_scale, df = prior_df)
}

.vf_unweighted_trend_fit <- function(expression, design) {
  raw <- lm.fit(design, t(expression))
  rank <- raw$rank
  if (rank < 1L || raw$df.residual < 1L) stop("design has no usable residual degrees of freedom")
  coefficients <- t(raw$coefficients)
  residual_rows <- seq.int(rank + 1L, nrow(design))
  sigma <- sqrt(colMeans(raw$effects[residual_rows, , drop = FALSE]^2))
  list(coefficients = coefficients, sigma = sigma, rank = rank)
}

.vf_weighted_fit <- function(expression, design, weights) {
  genes <- nrow(expression)
  terms <- ncol(design)
  coefficients <- matrix(NA_real_, genes, terms)
  unscaled <- matrix(NA_real_, genes, terms)
  sigma <- rep_len(NA_real_, genes)
  residual_df <- integer(genes)
  for (gene in seq_len(genes)) {
    fitted <- lm.wfit(design, expression[gene, ], weights[gene, ])
    rank <- fitted$rank
    coefficients[gene, ] <- fitted$coefficients
    unscaled[gene, seq_len(rank)] <- sqrt(diag(chol2inv(fitted$qr$qr, size = rank)))
    residual_df[[gene]] <- fitted$df.residual
    if (fitted$df.residual > 0L) {
      residual_effects <- fitted$effects[-seq_len(rank)]
      sigma[[gene]] <- sqrt(mean(residual_effects^2))
    }
  }
  list(
    coefficients = coefficients,
    stdev.unscaled = unscaled,
    sigma = sigma,
    df.residual = residual_df
  )
}

.vf_contrast_scale <- function(stdev.unscaled, design, contrast) {
  design_qr <- qr(design)
  covariance <- chol2inv(design_qr$qr, size = design_qr$rank)
  correlation <- cov2cor(covariance)
  below_diagonal <- correlation[lower.tri(correlation)]
  orthogonal <- length(below_diagonal) == 0L || all(abs(below_diagonal) < 1e-14)
  if (orthogonal) {
    return(sqrt(drop(stdev.unscaled^2 %*% contrast^2)))
  }
  factor <- chol(correlation)
  result <- numeric(nrow(stdev.unscaled))
  for (gene in seq_len(nrow(stdev.unscaled))) {
    scaled_contrast <- stdev.unscaled[gene, ] * contrast
    result[[gene]] <- sqrt(sum((factor %*% scaled_contrast)^2))
  }
  result
}

voomFit <- function(
    counts,
    design,
    contrast,
    lib.size = NULL,
    span = 0.5,
    norm.method = c("TMM", "RLE", "upperquartile", "none")) {
  norm.method <- match.arg(norm.method)
  .vf_check_inputs(counts, design, contrast, lib.size, span, norm.method)

  counts <- unname(as.matrix(counts))
  storage.mode(counts) <- "double"
  design <- unname(as.matrix(design))
  storage.mode(design) <- "double"
  contrast <- as.double(contrast)
  if (is.null(lib.size)) lib.size <- colSums(counts)
  lib.size <- as.double(lib.size)

  norm.factors <- calcNormFactors.default(
    counts,
    lib.size = lib.size,
    method = norm.method
  )
  effective_size <- lib.size * norm.factors
  log_cpm <- t(log2(t(counts + 0.5) / (effective_size + 1) * 1e6))

  trend_fit <- .vf_unweighted_trend_fit(log_cpm, design)
  average_expression <- rowMeans(log_cpm)
  trend_x <- average_expression + mean(log2(effective_size + 1)) - log2(1e6)
  trend_y <- sqrt(trend_fit$sigma)
  nonzero <- rowSums(counts) > 0
  smoothed <- lowess(trend_x[nonzero], trend_y[nonzero], f = span)
  variance_curve <- approxfun(smoothed, rule = 2, ties = list("ordered", mean))

  fitted_log_cpm <- trend_fit$coefficients %*% t(design)
  fitted_cpm <- 2^fitted_log_cpm
  fitted_counts <- 1e-6 * t(t(fitted_cpm) * (effective_size + 1))
  weights <- 1 / variance_curve(log2(fitted_counts))^4
  dim(weights) <- dim(log_cpm)

  weighted <- .vf_weighted_fit(log_cpm, design, weights)
  contrast_coefficients <- drop(weighted$coefficients %*% contrast)
  contrast_unscaled <- .vf_contrast_scale(weighted$stdev.unscaled, design, contrast)

  prior <- .vf_variance_prior(weighted$sigma^2, weighted$df.residual)
  if (is.finite(prior$df)) {
    posterior_variance <- (
      weighted$df.residual * weighted$sigma^2 + prior$df * prior$scale
    ) / (weighted$df.residual + prior$df)
  } else {
    posterior_variance <- rep_len(prior$scale, nrow(counts))
  }
  total_df <- pmin(weighted$df.residual + prior$df, sum(weighted$df.residual))
  moderated_t <- contrast_coefficients / contrast_unscaled / sqrt(posterior_variance)
  p_value <- 2 * pt(-abs(moderated_t), df = total_df)

  list(
    logCPM = unname(log_cpm),
    weights = unname(weights),
    coefficients = unname(weighted$coefficients),
    contrast.coefficients = unname(as.double(contrast_coefficients)),
    t = unname(as.double(moderated_t)),
    p.value = unname(as.double(p_value)),
    df.total = unname(as.double(total_df)),
    norm.factors = unname(as.double(norm.factors))
  )
}
