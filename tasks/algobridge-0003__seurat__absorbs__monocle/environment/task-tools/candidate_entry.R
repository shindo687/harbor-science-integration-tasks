args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) quit(status = 2L)
module_path <- args[[1]]
input_path <- args[[2]]
output_path <- args[[3]]

normalize_rows <- function(rows, mode) {
  if (!is.list(rows) || length(rows) == 0L) stop("matrix rows must be non-empty")
  widths <- vapply(rows, length, integer(1))
  if (length(unique(widths)) != 1L) stop("ragged matrix")
  value <- do.call(rbind, lapply(rows, unlist, use.names = FALSE))
  storage.mode(value) <- mode
  value
}

result <- tryCatch({
  suppressPackageStartupMessages(library(igraph))
  case <- jsonlite::read_json(input_path, simplifyVector = FALSE)
  if (!is.list(case) || !identical(case$schema, "seurat-monocle-principal-graph-v1")) {
    stop("unsupported schema")
  }
  embedding <- normalize_rows(case$embedding, "double")
  vertices <- normalize_rows(case$principal_vertices, "double")
  edges <- normalize_rows(case$principal_edges, "character")
  dimensions <- as.integer(case$dimensions)
  if (length(dimensions) != 1L || is.na(dimensions) ||
      !(dimensions %in% c(2L, 3L)) ||
      ncol(embedding) != dimensions || ncol(vertices) != dimensions) {
    stop("dimensions must be 2 or 3 and consistent")
  }
  cell_names <- unlist(case$cell_names, use.names = FALSE)
  vertex_names <- unlist(case$vertex_names, use.names = FALSE)
  rownames(embedding) <- cell_names
  rownames(vertices) <- vertex_names
  source(module_path, local = .GlobalEnv, chdir = FALSE)
  if (!exists("PrincipalGraphPseudotime", mode = "function", inherits = FALSE)) {
    stop("candidate did not define PrincipalGraphPseudotime")
  }
  answer <- PrincipalGraphPseudotime(
    embedding = embedding,
    principal_vertices = vertices,
    principal_edges = edges,
    root_vertices = unlist(case$root_vertices, use.names = FALSE),
    root_cells = unlist(case$root_cells, use.names = FALSE)
  )
  if (!is.list(answer) || !identical(answer$status, "ok")) {
    list(status = if (is.list(answer) && identical(answer$status, "invalid_input"))
      "invalid_input" else "invalid_output")
  } else {
    required_cells <- c("pseudotime", "closest_vertex", "cell_state")
    for (key in required_cells) {
      value <- answer[[key]]
      if (is.null(names(value)) || !setequal(names(value), cell_names)) {
        stop(paste(key, "must be named for every cell"))
      }
    }
    if (is.null(names(answer$vertex_role)) ||
        !setequal(names(answer$vertex_role), vertex_names)) {
      stop("vertex_role must be named for every vertex")
    }
    pseudotime <- as.numeric(answer$pseudotime[cell_names])
    if (any(!is.finite(pseudotime))) stop("pseudotime must be finite")
    list(
      status = "ok",
      cell_names = cell_names,
      pseudotime = pseudotime,
      closest_vertex = unname(as.character(answer$closest_vertex[cell_names])),
      cell_state = unname(as.character(answer$cell_state[cell_names])),
      vertex_names = vertex_names,
      vertex_role = unname(as.character(answer$vertex_role[vertex_names])),
      root_vertices = unname(as.character(answer$root_vertices))
    )
  }
}, error = function(error) {
  list(status = "invalid_input", error = conditionMessage(error))
})

jsonlite::write_json(result, output_path, auto_unbox = TRUE, digits = 17,
                     null = "null", na = "null")
