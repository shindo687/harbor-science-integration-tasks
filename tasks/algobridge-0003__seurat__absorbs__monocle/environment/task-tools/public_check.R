suppressPackageStartupMessages(library(jsonlite))

source("/opt/task-tools/candidate_runner.R", local = .GlobalEnv)

PSEUDOTIME_TOL <- 1e-8

matches <- function(expected, actual) {
  if (!identical(expected$status, actual$status)) return(FALSE)
  if (!identical(expected$status, "ok")) return(TRUE)
  numeric_ok <- is.numeric(actual$pseudotime) &&
    length(actual$pseudotime) == length(expected$pseudotime) &&
    all(is.finite(actual$pseudotime)) &&
    max(abs(expected$pseudotime - actual$pseudotime)) <= PSEUDOTIME_TOL
  numeric_ok &&
    identical(expected$cell_names, actual$cell_names) &&
    identical(expected$closest_vertex, actual$closest_vertex) &&
    identical(expected$cell_state, actual$cell_state) &&
    identical(expected$vertex_names, actual$vertex_names) &&
    identical(expected$vertex_role, actual$vertex_role) &&
    identical(expected$root_vertices, actual$root_vertices)
}

inputs <- sort(list.files(
  "/public-cases", pattern = "\\.input\\.json$", full.names = TRUE
))
passed <- 0L
for (input in inputs) {
  expected_path <- sub("\\.input\\.json$", ".expected.json", input)
  case <- read_json(input, simplifyVector = FALSE)
  expected <- read_json(expected_path, simplifyVector = TRUE)
  actual <- tryCatch(
    run_candidate(case),
    error = function(error) list(status = "error", error = conditionMessage(error))
  )
  ok <- matches(expected, actual)
  passed <- passed + as.integer(ok)
  cat(sprintf("%s %s: %s\n", if (ok) "PASS" else "FAIL",
              basename(input), actual$status))
}
cat(sprintf("public examples: %d/%d\n", passed, length(inputs)))
quit(status = if (passed == length(inputs) && length(inputs) == 5L) 0L else 1L)
