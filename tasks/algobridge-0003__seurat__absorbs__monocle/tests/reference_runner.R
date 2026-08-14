suppressPackageStartupMessages(library(monocle3))
suppressPackageStartupMessages(library(igraph))

validate_case <- function(case) {
  if (!is.list(case) || !identical(case$schema, SCHEMA)) stop("unsupported schema")
  mats <- case_matrices(case)
  embedding <- mats$embedding
  vertices <- mats$vertices
  edges <- mats$edges
  dimensions <- as.integer(case$dimensions)
  if (!(dimensions %in% c(2L, 3L)) || ncol(embedding) != dimensions ||
      ncol(vertices) != dimensions) stop("dimensions must be 2 or 3 and consistent")
  if (nrow(embedding) < 3L || nrow(embedding) > 96L) stop("cell count out of range")
  if (nrow(vertices) < 2L || nrow(vertices) > 32L) stop("vertex count out of range")
  if (nrow(edges) < 1L || nrow(edges) > 64L || ncol(edges) != 2L) stop("edge count out of range")
  if (length(rownames(embedding)) != nrow(embedding) || anyDuplicated(rownames(embedding)) ||
      any(!nzchar(rownames(embedding)))) stop("cell names must be unique")
  expected_vertices <- paste0("Y_", seq_len(nrow(vertices)))
  if (!identical(rownames(vertices), expected_vertices)) stop("vertex names must be sequential Y_1..Y_n")
  if (any(!is.finite(embedding)) || any(!is.finite(vertices)) ||
      any(abs(embedding) > 1e4) || any(abs(vertices) > 1e4)) stop("coordinates must be finite and bounded")
  if (any(edges[, 1] == edges[, 2]) || any(!edges %in% rownames(vertices))) stop("invalid edge endpoint")
  keys <- apply(edges, 1, function(x) paste(sort(x), collapse = "|"))
  if (anyDuplicated(keys)) stop("duplicate undirected edge")
  edge_lengths <- apply(edges, 1, function(x) sqrt(sum((vertices[x[1], ] - vertices[x[2], ])^2)))
  if (any(edge_lengths <= 1e-12)) stop("zero-length principal edge")
  root_vertices <- unlist(case$root_vertices, use.names = FALSE)
  root_cells <- unlist(case$root_cells, use.names = FALSE)
  if ((length(root_vertices) > 0L) == (length(root_cells) > 0L)) stop("specify exactly one root mode")
  if (anyDuplicated(root_vertices) || anyDuplicated(root_cells)) stop("duplicate roots")
  if (length(root_vertices) && any(!root_vertices %in% rownames(vertices))) stop("unknown root vertex")
  if (length(root_cells) && any(!root_cells %in% rownames(embedding))) stop("unknown root cell")
  graph <- igraph::graph_from_data_frame(
    data.frame(from = edges[, 1], to = edges[, 2]), directed = FALSE,
    vertices = data.frame(name = rownames(vertices))
  )
  if (any(igraph::degree(graph) == 0)) stop("isolated principal vertex")
  distances <- vapply(seq_len(nrow(embedding)), function(i) {
    sqrt(colSums((t(vertices) - embedding[i, ])^2))
  }, numeric(nrow(vertices)))
  closest_index <- apply(distances, 2, which.min)
  names(closest_index) <- rownames(embedding)
  membership <- igraph::components(graph)$membership
  if (length(root_cells)) root_vertices <- unique(paste0("Y_", closest_index[root_cells]))
  rooted_components <- unique(unname(membership[root_vertices]))
  if (!setequal(rooted_components, unique(unname(membership)))) stop("every component needs a root")
  list(case = case, embedding = embedding, vertices = vertices, edges = edges,
       graph = graph, closest_index = closest_index, membership = membership,
       root_vertices = root_vertices, root_cells = root_cells)
}

vertex_states <- function(graph, root_vertices, branch_vertices) {
  vertex_names <- names(igraph::V(graph))
  roles <- setNames(rep("internal", length(vertex_names)), vertex_names)
  roles[names(which(igraph::degree(graph) == 1L))] <- "leaf"
  roles[branch_vertices] <- "branch"
  roles[root_vertices] <- "root"
  cut_vertices <- unique(c(root_vertices, branch_vertices))
  states <- setNames(rep(NA_character_, length(vertex_names)), vertex_names)
  states[cut_vertices] <- paste0("node:", cut_vertices)
  remaining <- setdiff(vertex_names, cut_vertices)
  if (length(remaining)) {
    subgraph <- igraph::induced_subgraph(graph, remaining)
    groups <- igraph::components(subgraph)$membership
    for (group in unique(groups)) {
      members <- names(groups)[groups == group]
      original_order <- match(members, vertex_names)
      label <- paste0("segment:", members[which.min(original_order)])
      states[members] <- label
    }
  }
  list(roles = roles, states = states)
}

run_reference <- function(case) {
  validated <- validate_case(case)
  embedding <- validated$embedding
  vertices <- validated$vertices
  graph <- validated$graph
  cells <- rownames(embedding)
  counts <- matrix(1, nrow = 1, ncol = nrow(embedding),
                   dimnames = list("G1", cells))
  cds <- monocle3::new_cell_data_set(
    counts,
    cell_metadata = data.frame(row.names = cells),
    gene_metadata = data.frame(gene_short_name = "G1", row.names = "G1")
  )
  SingleCellExperiment::reducedDims(cds)$UMAP <- embedding
  cds@principal_graph[["UMAP"]] <- graph
  cds@principal_graph_aux[["UMAP"]]$dp_mst <- t(vertices)
  partitions <- factor(unname(validated$membership[paste0("Y_", validated$closest_index)]))
  names(partitions) <- cells
  clusters <- factor(rep(1L, length(cells)))
  names(clusters) <- cells
  cds@clusters[["UMAP"]] <- list(partitions = partitions, clusters = clusters)
  cds <- suppressWarnings(monocle3:::project2MST(
    cds,
    monocle3:::project_point_to_line_segment,
    orthogonal_proj_tip = FALSE,
    verbose = FALSE,
    reduction_method = "UMAP",
    rge_res_Y = t(vertices)
  ))
  if (length(validated$root_cells)) {
    cds <- monocle3::order_cells(cds, root_cells = validated$root_cells)
  } else {
    cds <- monocle3::order_cells(cds, root_pr_nodes = validated$root_vertices)
  }
  pseudotime <- monocle3::pseudotime(cds)
  if (any(!is.finite(pseudotime))) stop("reference produced unreachable cells")
  closest_raw <- cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex[, 1]
  closest <- setNames(names(igraph::V(graph))[closest_raw], names(closest_raw))
  roots <- names(monocle3:::root_nodes(cds))
  branches <- names(monocle3:::branch_nodes(cds))
  state_info <- vertex_states(graph, roots, branches)
  list(
    status = "ok",
    cell_names = cells,
    pseudotime = unname(as.numeric(pseudotime[cells])),
    closest_vertex = unname(closest[cells]),
    cell_state = unname(state_info$states[closest[cells]]),
    vertex_names = rownames(vertices),
    vertex_role = unname(state_info$roles[rownames(vertices)]),
    root_vertices = roots
  )
}
