#' Project cells onto a principal graph and compute pseudotime
#'
#' @param embedding Named cell-by-dimension numeric matrix.
#' @param principal_vertices Named vertex-by-dimension numeric matrix.
#' @param principal_edges Two-column matrix of undirected vertex names.
#' @param root_vertices Principal vertices used to orient pseudotime.
#' @param root_cells Cells whose nearest principal vertices orient pseudotime.
#' @return A named list containing projection, pseudotime, state, and role data.
#' @export

PrincipalGraphPseudotime <- function(embedding, principal_vertices,
                                     principal_edges, root_vertices = character(),
                                     root_cells = character()) {
  invalid <- function(message) list(status = "invalid_input", error = message)
  tryCatch({
    embedding <- as.matrix(embedding)
    principal_vertices <- as.matrix(principal_vertices)
    principal_edges <- matrix(as.character(principal_edges), ncol = 2)
    storage.mode(embedding) <- "double"
    storage.mode(principal_vertices) <- "double"
    cell_names <- rownames(embedding)
    vertex_names <- rownames(principal_vertices)
    dimensions <- ncol(embedding)
    if (!(dimensions %in% c(2L, 3L)) || ncol(principal_vertices) != dimensions) stop("unsupported dimensions")
    if (nrow(embedding) < 3L || nrow(embedding) > 96L ||
        nrow(principal_vertices) < 2L || nrow(principal_vertices) > 32L ||
        nrow(principal_edges) < 1L || nrow(principal_edges) > 64L) stop("size out of range")
    if (is.null(cell_names) || anyDuplicated(cell_names) || any(!nzchar(cell_names))) stop("invalid cell names")
    if (!identical(vertex_names, paste0("Y_", seq_len(nrow(principal_vertices))))) stop("invalid vertex names")
    if (any(!is.finite(embedding)) || any(!is.finite(principal_vertices)) ||
        any(abs(embedding) > 1e4) || any(abs(principal_vertices) > 1e4)) stop("invalid coordinates")
    if (any(principal_edges[, 1] == principal_edges[, 2]) ||
        any(!principal_edges %in% vertex_names)) stop("invalid edge")
    edge_keys <- apply(principal_edges, 1, function(x) paste(sort(x), collapse = "|"))
    if (anyDuplicated(edge_keys)) stop("duplicate edge")
    principal_lengths <- apply(principal_edges, 1, function(x) {
      sqrt(sum((principal_vertices[x[1], ] - principal_vertices[x[2], ])^2))
    })
    if (any(principal_lengths <= 1e-12)) stop("zero-length edge")
    root_vertices <- as.character(root_vertices)
    root_cells <- as.character(root_cells)
    if ((length(root_vertices) > 0L) == (length(root_cells) > 0L)) stop("invalid root mode")
    if (anyDuplicated(root_vertices) || anyDuplicated(root_cells) ||
        any(!root_vertices %in% vertex_names) || any(!root_cells %in% cell_names)) stop("invalid roots")

    graph <- igraph::graph_from_data_frame(
      data.frame(from = principal_edges[, 1], to = principal_edges[, 2]),
      directed = FALSE, vertices = data.frame(name = vertex_names)
    )
    if (any(igraph::degree(graph) == 0L)) stop("isolated vertex")
    squared_distances <- vapply(seq_len(nrow(embedding)), function(i) {
      sqrt(colSums((t(principal_vertices) - embedding[i, ])^2))
    }, numeric(nrow(principal_vertices)))
    closest_index <- apply(squared_distances, 2, which.min)
    names(closest_index) <- cell_names
    closest_vertex <- setNames(vertex_names[closest_index], cell_names)
    membership <- igraph::components(graph)$membership
    if (length(root_cells)) root_vertices <- unique(paste0("Y_", closest_index[root_cells]))
    if (!setequal(unique(unname(membership[root_vertices])), unique(unname(membership)))) stop("unrooted component")

    projected <- matrix(0, nrow(embedding), dimensions,
                        dimnames = list(cell_names, NULL))
    edge_for_cell <- matrix("", nrow(embedding), 2,
                            dimnames = list(cell_names, c("source", "target")))
    for (i in seq_len(nrow(embedding))) {
      near <- closest_vertex[[i]]
      neighbors <- names(igraph::neighbors(graph, near, mode = "all"))
      candidates <- lapply(neighbors, function(neighbor) {
        a <- principal_vertices[near, ]
        b <- principal_vertices[neighbor, ]
        direction <- b - a
        fraction <- sum((embedding[i, ] - a) * direction) / sum(direction^2)
        fraction <- max(0, min(1, fraction))
        a + fraction * direction
      })
      candidate_matrix <- do.call(rbind, candidates)
      distances <- sqrt(rowSums((candidate_matrix - matrix(
        embedding[i, ], nrow(candidate_matrix), dimensions, byrow = TRUE
      ))^2))
      choice <- which.min(distances)
      projected[i, ] <- candidate_matrix[choice, ]
      edge_for_cell[i, ] <- sort(c(near, neighbors[choice]))
    }

    groups <- paste(edge_for_cell[, 1], edge_for_cell[, 2], sep = "_")
    distance_to_source <- vapply(seq_len(nrow(embedding)), function(i) {
      sqrt(sum((projected[i, ] - principal_vertices[edge_for_cell[i, 1], ])^2))
    }, numeric(1))
    ordering <- order(groups, distance_to_source)
    chain_from <- chain_to <- character(nrow(embedding))
    chain_weight <- numeric(nrow(embedding))
    chain_component <- integer(nrow(embedding))
    previous_group <- ""
    previous_cell <- ""
    for (position in seq_along(ordering)) {
      i <- ordering[position]
      if (!identical(groups[i], previous_group)) {
        chain_from[position] <- edge_for_cell[i, 1]
      } else {
        chain_from[position] <- previous_cell
      }
      chain_to[position] <- cell_names[i]
      chain_component[position] <- unname(membership[edge_for_cell[i, 1]])
      from_point <- if (chain_from[position] %in% vertex_names) {
        principal_vertices[chain_from[position], ]
      } else {
        projected[chain_from[position], ]
      }
      # The bounded interface defines cell-chain distance from the signed
      # coordinate sum; principal-graph edge lengths remain Euclidean.
      chain_weight[position] <- abs(sum(from_point - projected[i, ]))
      previous_group <- groups[i]
      previous_cell <- cell_names[i]
    }
    for (component in unique(chain_component)) {
      selected <- which(chain_component == component)
      positive <- chain_weight[selected][chain_weight[selected] > 0]
      if (!length(positive)) stop("degenerate cell projection")
      chain_weight[selected] <- chain_weight[selected] + min(positive)
    }
    graph_edges <- data.frame(
      from = c(chain_from, principal_edges[, 1]),
      to = c(chain_to, principal_edges[, 2]),
      weight = c(chain_weight, principal_lengths),
      stringsAsFactors = FALSE
    )
    augmented <- igraph::graph_from_data_frame(graph_edges, directed = FALSE)

    root_cell_ids <- vapply(root_vertices, function(root) {
      distances <- sqrt(rowSums((embedding - matrix(
        principal_vertices[root, ], nrow(embedding), dimensions, byrow = TRUE
      ))^2))
      cell_names[which.min(distances)]
    }, character(1))
    distance_matrix <- igraph::distances(augmented, v = root_cell_ids,
                                         to = cell_names, weights = igraph::E(augmented)$weight)
    if (length(root_cell_ids) == 1L) {
      pseudotime <- as.numeric(distance_matrix[1, ])
    } else {
      pseudotime <- apply(distance_matrix, 2, min)
    }
    names(pseudotime) <- cell_names
    if (any(!is.finite(pseudotime))) stop("unreachable cell")

    roles <- setNames(rep("internal", length(vertex_names)), vertex_names)
    roles[names(which(igraph::degree(graph) == 1L))] <- "leaf"
    branches <- setdiff(names(which(igraph::degree(graph) > 2L)), root_vertices)
    roles[branches] <- "branch"
    roles[root_vertices] <- "root"
    cut_vertices <- unique(c(root_vertices, branches))
    states <- setNames(rep(NA_character_, length(vertex_names)), vertex_names)
    states[cut_vertices] <- paste0("node:", cut_vertices)
    remaining <- setdiff(vertex_names, cut_vertices)
    if (length(remaining)) {
      subgraph <- igraph::induced_subgraph(graph, remaining)
      segments <- igraph::components(subgraph)$membership
      for (segment in unique(segments)) {
        members <- names(segments)[segments == segment]
        label <- paste0("segment:", members[which.min(match(members, vertex_names))])
        states[members] <- label
      }
    }
    list(
      status = "ok",
      pseudotime = pseudotime,
      closest_vertex = closest_vertex,
      cell_state = setNames(unname(states[closest_vertex]), cell_names),
      vertex_role = roles,
      root_vertices = root_vertices
    )
  }, error = function(error) invalid(conditionMessage(error)))
}
