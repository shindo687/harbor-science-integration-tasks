CANDIDATE_MODULE <- normalizePath(
  Sys.getenv("PSEUDOTIME_CANDIDATE_FILE", "/testbed/R/principal_graph_pseudotime.R"),
  mustWork = FALSE
)
CANDIDATE_ENTRY <- normalizePath(
  Sys.getenv("PSEUDOTIME_CANDIDATE_ENTRY", "/opt/candidate-runner/candidate_entry.R"),
  mustWork = FALSE
)
CANDIDATE_UID <- "10001"

if (!exists("write_case_json", mode = "function")) {
  write_case_json <- function(case, path) {
    jsonlite::write_json(case, path, auto_unbox = TRUE, pretty = TRUE,
                         digits = 17, null = "null", na = "null")
  }
}

run_candidate <- function(case) {
  if (!file.exists(CANDIDATE_MODULE)) {
    return(list(status = "invalid_input", error = "missing R/principal_graph_pseudotime.R"))
  }
  work <- tempfile("pseudotime-candidate-", tmpdir = "/tmp")
  dir.create(work, mode = "0777")
  Sys.chmod(work, mode = "0777", use_umask = FALSE)
  on.exit(unlink(work, recursive = TRUE, force = TRUE), add = TRUE)
  input <- file.path(work, "case.json")
  output <- file.path(work, "result.json")
  write_case_json(case, input)
  Sys.chmod(input, mode = "0644")
  effective_uid <- suppressWarnings(as.integer(system("id -u", intern = TRUE)))
  no_privdrop <- identical(Sys.getenv("PSEUDOTIME_NO_PRIVDROP"), "1") ||
    is.na(effective_uid) || effective_uid != 0L
  rscript <- Sys.which("Rscript")
  if (no_privdrop) {
    command <- rscript
    arguments <- c(CANDIDATE_ENTRY, CANDIDATE_MODULE, input, output)
  } else {
    command <- "/usr/bin/setpriv"
    arguments <- c(
      "--nnp", "/usr/bin/setuidgid", CANDIDATE_UID, rscript,
      CANDIDATE_ENTRY, CANDIDATE_MODULE, input, output
    )
  }
  process_output <- tryCatch(
    system2(command, arguments, stdout = TRUE, stderr = TRUE, timeout = 120),
    error = function(error) structure(conditionMessage(error), status = 1L)
  )
  status <- attr(process_output, "status")
  if (is.null(status)) status <- 0L
  if (status != 0L || !file.exists(output)) {
    return(list(status = "invalid_input", error = paste(process_output, collapse = "\n")))
  }
  tryCatch(
    jsonlite::read_json(output, simplifyVector = TRUE),
    error = function(error) list(status = "invalid_input", error = conditionMessage(error))
  )
}
