SCHEMA <- "seurat-monocle-principal-graph-v1"

matrix_with_names <- function(values, names) {
  value <- as.matrix(values)
  storage.mode(value) <- "double"
  rownames(value) <- names
  value
}

make_case <- function(name, vertices, edges, embedding,
                      root_vertices = character(), root_cells = character()) {
  vertices <- as.matrix(vertices)
  embedding <- as.matrix(embedding)
  edges <- matrix(as.character(edges), ncol = 2)
  storage.mode(vertices) <- "double"
  storage.mode(embedding) <- "double"
  if (is.null(rownames(vertices))) {
    rownames(vertices) <- paste0("Y_", seq_len(nrow(vertices)))
  }
  if (is.null(rownames(embedding))) {
    rownames(embedding) <- paste0("C", seq_len(nrow(embedding)))
  }
  list(
    name = name,
    schema = SCHEMA,
    dimensions = ncol(vertices),
    cell_names = rownames(embedding),
    embedding = unname(split(embedding, row(embedding))),
    vertex_names = rownames(vertices),
    principal_vertices = unname(split(vertices, row(vertices))),
    principal_edges = unname(split(edges, row(edges))),
    root_vertices = as.character(root_vertices),
    root_cells = as.character(root_cells)
  )
}

case_matrices <- function(case) {
  rows_to_matrix <- function(rows, mode = "double") {
    if (!is.list(rows) || length(rows) == 0L) stop("matrix rows must be non-empty")
    widths <- vapply(rows, length, integer(1))
    if (length(unique(widths)) != 1L) stop("ragged matrix")
    value <- do.call(rbind, lapply(rows, unlist, use.names = FALSE))
    storage.mode(value) <- mode
    value
  }
  embedding <- rows_to_matrix(case$embedding, "double")
  vertices <- rows_to_matrix(case$principal_vertices, "double")
  edges <- rows_to_matrix(case$principal_edges, "character")
  rownames(embedding) <- unlist(case$cell_names, use.names = FALSE)
  rownames(vertices) <- unlist(case$vertex_names, use.names = FALSE)
  list(embedding = embedding, vertices = vertices, edges = edges)
}

cells_on_edges <- function(vertices, edges, points = 3L, phase = 0) {
  vertices <- as.matrix(vertices)
  edges <- matrix(as.character(edges), ncol = 2)
  output <- list()
  index <- 0L
  for (edge_index in seq_len(nrow(edges))) {
    a <- vertices[edges[edge_index, 1], ]
    b <- vertices[edges[edge_index, 2], ]
    direction <- b - a
    for (point_index in seq_len(points)) {
      index <- index + 1L
      t <- (point_index - 0.35) / (points + 0.3)
      point <- a + t * direction
      magnitude <- 0.025 * sin(index * 1.71 + phase)
      if (ncol(vertices) == 2L) {
        normal <- c(-direction[2], direction[1])
        if (sqrt(sum(normal^2)) > 0) normal <- normal / sqrt(sum(normal^2))
      } else {
        normal <- c(-direction[2], direction[1], 0)
        if (sqrt(sum(normal^2)) <= 1e-12) normal <- c(0, -direction[3], direction[2])
        if (sqrt(sum(normal^2)) > 0) normal <- normal / sqrt(sum(normal^2))
      }
      output[[index]] <- point + magnitude * normal
    }
  }
  embedding <- do.call(rbind, output)
  rownames(embedding) <- paste0("C", seq_len(nrow(embedding)))
  embedding
}

line_graph <- function(lengths = c(1, 1, 1), dimensions = 2L) {
  x <- c(0, cumsum(lengths))
  vertices <- cbind(x, rep(0, length(x)))
  if (dimensions == 3L) vertices <- cbind(vertices, seq_along(x) * 0.17)
  rownames(vertices) <- paste0("Y_", seq_len(nrow(vertices)))
  edges <- cbind(
    paste0("Y_", seq_len(nrow(vertices) - 1L)),
    paste0("Y_", seq_len(nrow(vertices) - 1L) + 1L)
  )
  list(vertices = vertices, edges = edges)
}

y_graph <- function(scale = 1, dimensions = 2L) {
  vertices <- scale * rbind(
    c(0, 0), c(1, 0), c(2, 0), c(3, 0.9), c(3, -0.9)
  )
  if (dimensions == 3L) vertices <- cbind(vertices, c(0, 0.1, 0.2, 0.45, -0.35))
  rownames(vertices) <- paste0("Y_", seq_len(nrow(vertices)))
  edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"),
                 c("Y_3", "Y_4"), c("Y_3", "Y_5"))
  list(vertices = vertices, edges = edges)
}

public_cases <- function() {
  line <- line_graph(c(0.8, 1.2, 0.7))
  y <- y_graph()
  curved_vertices <- rbind(c(0, 0), c(0.8, 0.25), c(1.6, 0.1), c(2.4, 0.65))
  rownames(curved_vertices) <- paste0("Y_", 1:4)
  curved_edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"), c("Y_3", "Y_4"))
  cycle_vertices <- rbind(c(0, 0), c(1, 0), c(1, 1), c(0, 1))
  rownames(cycle_vertices) <- paste0("Y_", 1:4)
  cycle_edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"),
                       c("Y_3", "Y_4"), c("Y_4", "Y_1"))
  split_vertices <- rbind(c(0, 0), c(1, 0), c(5, 1), c(6.2, 1))
  rownames(split_vertices) <- paste0("Y_", 1:4)
  split_edges <- rbind(c("Y_1", "Y_2"), c("Y_3", "Y_4"))
  list(
    make_case("public_line_root_vertex", line$vertices, line$edges,
              cells_on_edges(line$vertices, line$edges, 3), root_vertices = "Y_1"),
    make_case("public_y_branch", y$vertices, y$edges,
              cells_on_edges(y$vertices, y$edges, 3, 0.4), root_vertices = "Y_1"),
    make_case("public_curved_root_cell", curved_vertices, curved_edges,
              cells_on_edges(curved_vertices, curved_edges, 3, 0.8), root_cells = "C1"),
    make_case("public_cycle", cycle_vertices, cycle_edges,
              cells_on_edges(cycle_vertices, cycle_edges, 2, 1.1), root_vertices = "Y_1"),
    make_case("public_two_components", split_vertices, split_edges,
              cells_on_edges(split_vertices, split_edges, 4, 1.7),
              root_vertices = c("Y_1", "Y_3"))
  )
}

hidden_cases <- function() {
  long <- line_graph(c(0.3, 0.9, 1.5, 0.45, 1.1))
  y <- y_graph(1.3)
  y3 <- y_graph(0.8, 3L)
  star_vertices <- rbind(c(0, 0), c(1, 0), c(2, 0), c(1, 1.2), c(1, -1.1), c(0.2, 1.1))
  rownames(star_vertices) <- paste0("Y_", 1:6)
  star_edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"),
                      c("Y_2", "Y_4"), c("Y_2", "Y_5"), c("Y_4", "Y_6"))
  triangle_vertices <- rbind(c(0, 0), c(1.4, 0), c(0.7, 1.15))
  rownames(triangle_vertices) <- paste0("Y_", 1:3)
  triangle_edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"), c("Y_3", "Y_1"))
  tail_vertices <- rbind(c(0, 0), c(1, 0), c(1, 1), c(0, 1), c(2, 0), c(3, 0.4))
  rownames(tail_vertices) <- paste0("Y_", 1:6)
  tail_edges <- rbind(c("Y_1", "Y_2"), c("Y_2", "Y_3"), c("Y_3", "Y_4"),
                      c("Y_4", "Y_1"), c("Y_2", "Y_5"), c("Y_5", "Y_6"))
  split_vertices <- rbind(c(-3, 0), c(-2, 0.4), c(3, -0.5), c(4, 0.1), c(5, -0.2))
  rownames(split_vertices) <- paste0("Y_", 1:5)
  split_edges <- rbind(c("Y_1", "Y_2"), c("Y_3", "Y_4"), c("Y_4", "Y_5"))
  irregular <- line_graph(c(0.12, 2.4, 0.33, 1.7))
  three_vertices <- rbind(c(-6, 0), c(-5, 0), c(0, 3), c(0.8, 3.2), c(6, -1), c(7.5, -1))
  rownames(three_vertices) <- paste0("Y_", 1:6)
  three_edges <- rbind(c("Y_1", "Y_2"), c("Y_3", "Y_4"), c("Y_5", "Y_6"))
  perm_base <- cells_on_edges(y$vertices, y$edges, 2, 2.2)
  permuted <- perm_base[c(5, 1, 7, 3, 8, 2, 6, 4), , drop = FALSE]
  rownames(permuted) <- paste0("C", seq_len(nrow(permuted)))
  near_tie <- rbind(c(0.49, 0.045), c(0.51, -0.052), c(1.48, 0.021),
                    c(1.52, -0.018), c(2.45, 0.031), c(2.62, -0.025))
  rownames(near_tie) <- paste0("C", 1:6)
  mid <- line_graph(c(0.7, 1.1, 0.9, 0.6))
  list(
    make_case("hidden_long_line", long$vertices, long$edges,
              cells_on_edges(long$vertices, long$edges, 3, 0.2), root_vertices = "Y_1"),
    make_case("hidden_middle_root", mid$vertices, mid$edges,
              cells_on_edges(mid$vertices, mid$edges, 3, 0.5), root_vertices = "Y_3"),
    make_case("hidden_y_reverse_root", y$vertices, y$edges,
              cells_on_edges(y$vertices, y$edges, 4, 0.9), root_vertices = "Y_5"),
    make_case("hidden_star", star_vertices, star_edges,
              cells_on_edges(star_vertices, star_edges, 3, 1.3), root_vertices = "Y_1"),
    make_case("hidden_three_dimensions", y3$vertices, y3$edges,
              cells_on_edges(y3$vertices, y3$edges, 3, 1.6), root_vertices = "Y_1"),
    make_case("hidden_triangle_cycle", triangle_vertices, triangle_edges,
              cells_on_edges(triangle_vertices, triangle_edges, 4, 0.7), root_vertices = "Y_2"),
    make_case("hidden_cycle_with_tail", tail_vertices, tail_edges,
              cells_on_edges(tail_vertices, tail_edges, 3, 1.9), root_vertices = "Y_4"),
    make_case("hidden_two_components_vertices", split_vertices, split_edges,
              cells_on_edges(split_vertices, split_edges, 3, 0.3),
              root_vertices = c("Y_1", "Y_3")),
    make_case("hidden_two_components_cells", split_vertices, split_edges,
              cells_on_edges(split_vertices, split_edges, 4, 0.6),
              root_cells = c("C1", "C5")),
    make_case("hidden_near_projection_ties", mid$vertices, mid$edges,
              near_tie, root_vertices = "Y_1"),
    make_case("hidden_irregular_lengths", irregular$vertices, irregular$edges,
              cells_on_edges(irregular$vertices, irregular$edges, 4, 1.1), root_vertices = "Y_5"),
    make_case("hidden_root_cell", long$vertices, long$edges,
              cells_on_edges(long$vertices, long$edges, 2, 1.5), root_cells = "C4"),
    make_case("hidden_cell_order", y$vertices, y$edges, permuted, root_vertices = "Y_1"),
    make_case("hidden_dense_edges", star_vertices, star_edges,
              cells_on_edges(star_vertices, star_edges, 5, 2.5), root_cells = "C1"),
    make_case("hidden_three_components", three_vertices, three_edges,
              cells_on_edges(three_vertices, three_edges, 3, 1.4),
              root_vertices = c("Y_1", "Y_3", "Y_5"))
  )
}

invalid_cases <- function() {
  base <- public_cases()[[1]]
  rows <- list()
  bad <- base; bad$schema <- "wrong"; rows$wrong_schema <- bad
  bad <- base; bad$dimensions <- 4L; rows$unsupported_dimensions <- bad
  bad <- base; bad$cell_names[[2]] <- bad$cell_names[[1]]; rows$duplicate_cells <- bad
  bad <- base; bad$vertex_names[[2]] <- "Y_9"; rows$nonsequential_vertices <- bad
  bad <- base; bad$principal_edges[[1]][[2]] <- "Y_99"; rows$unknown_edge_vertex <- bad
  bad <- base; bad$principal_edges[[1]][[2]] <- bad$principal_edges[[1]][[1]]; rows$self_loop <- bad
  bad <- base; bad$root_vertices <- list(); rows$missing_root <- bad
  bad <- base; bad$root_cells <- list("C1"); rows$two_root_modes <- bad
  bad <- base; bad$root_vertices <- list("Y_99"); rows$unknown_root <- bad
  split <- public_cases()[[5]]; split$root_vertices <- list("Y_1"); rows$unrooted_component <- split
  rows
}

permute_cells <- function(case, order) {
  mats <- case_matrices(case)
  old_names <- rownames(mats$embedding)
  mats$embedding <- mats$embedding[order, , drop = FALSE]
  root_cells <- unlist(case$root_cells)
  mapping <- setNames(paste0("C", seq_along(order)), old_names[order])
  rownames(mats$embedding) <- paste0("C", seq_len(nrow(mats$embedding)))
  if (length(root_cells)) root_cells <- unname(mapping[root_cells])
  make_case(paste0(case$name, "_permuted"), mats$vertices, mats$edges,
            mats$embedding, unlist(case$root_vertices), root_cells)
}

permute_edges <- function(case, order) {
  mats <- case_matrices(case)
  edges <- mats$edges[order, , drop = FALSE]
  flip <- seq_len(nrow(edges)) %% 2L == 0L
  edges[flip, ] <- edges[flip, 2:1, drop = FALSE]
  make_case(paste0(case$name, "_edge_order"), mats$vertices, edges,
            mats$embedding, unlist(case$root_vertices), unlist(case$root_cells))
}

metamorphic_pairs <- function() {
  edge_order <- public_cases()[[2]]
  perm <- public_cases()[[1]]
  list(
    list(name = "edge_order_and_direction", left = edge_order,
         right = permute_edges(edge_order, c(4, 2, 1, 3)), kind = "same"),
    list(name = "cell_permutation", left = perm,
         right = permute_cells(perm, c(7, 2, 5, 1, 9, 4, 8, 3, 6)), kind = "same_by_geometry")
  )
}

write_case_json <- function(case, path) {
  jsonlite::write_json(case, path, auto_unbox = TRUE, pretty = TRUE,
                       digits = 17, null = "null", na = "null")
}
