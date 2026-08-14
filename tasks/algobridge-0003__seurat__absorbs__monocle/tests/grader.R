suppressPackageStartupMessages(library(jsonlite))

source("/tests/cases.R", local = .GlobalEnv)
source("/tests/reference_runner.R", local = .GlobalEnv)
source("/opt/candidate-runner/candidate_runner.R", local = .GlobalEnv)

LOG_DIR <- Sys.getenv("VERIFIER_LOG_DIR", "/logs/verifier")
PSEUDOTIME_TOL <- 1e-8

finite_or_null <- function(value) {
  if (length(value) == 1L && is.finite(value)) as.numeric(value) else NULL
}

compare_outputs <- function(reference, candidate) {
  detail <- list(
    reference_status = reference$status,
    candidate_status = candidate$status
  )
  if (!identical(reference$status, candidate$status)) {
    detail$reason <- "status mismatch"
    return(list(passed = FALSE, detail = detail))
  }
  if (!identical(reference$status, "ok")) {
    return(list(passed = TRUE, detail = detail))
  }
  numeric_ok <- is.numeric(candidate$pseudotime) &&
    length(candidate$pseudotime) == length(reference$pseudotime) &&
    all(is.finite(candidate$pseudotime))
  error <- if (numeric_ok) {
    max(abs(reference$pseudotime - candidate$pseudotime))
  } else {
    Inf
  }
  categorical_ok <-
    identical(reference$cell_names, candidate$cell_names) &&
    identical(reference$closest_vertex, candidate$closest_vertex) &&
    identical(reference$cell_state, candidate$cell_state) &&
    identical(reference$vertex_names, candidate$vertex_names) &&
    identical(reference$vertex_role, candidate$vertex_role) &&
    identical(reference$root_vertices, candidate$root_vertices)
  passed <- numeric_ok && error <= PSEUDOTIME_TOL && categorical_ok
  detail$pseudotime_max_abs_error <- finite_or_null(error)
  detail$categorical_fields_exact <- categorical_ok
  if (!passed) detail$reason <- "scientific output mismatch"
  list(passed = passed, detail = detail)
}

safe_reference <- function(case) {
  tryCatch(
    run_reference(case),
    error = function(error) list(status = "invalid_input", error = conditionMessage(error))
  )
}

run_pair <- function(case) {
  list(reference = safe_reference(case), candidate = run_candidate(case))
}

audit_original_tree <- function(candidate_root, pristine_root) {
  excluded <- c("DESCRIPTION", "NAMESPACE")
  files <- list.files(
    pristine_root, recursive = TRUE, all.files = TRUE,
    full.names = FALSE, include.dirs = FALSE, no.. = TRUE
  )
  files <- setdiff(files, excluded)
  changed <- character()
  for (relative in files) {
    pristine <- file.path(pristine_root, relative)
    candidate <- file.path(candidate_root, relative)
    if (!file.exists(candidate) ||
        !identical(unname(tools::md5sum(pristine)), unname(tools::md5sum(candidate)))) {
      changed <- c(changed, relative)
    }
  }
  changed
}

source_audit <- function() {
  candidate_root <- "/testbed"
  pristine_root <- "/opt/pristine-host"
  module <- file.path(candidate_root, "R/principal_graph_pseudotime.R")
  findings <- character()
  if (!file.exists(module)) {
    return(list(passed = FALSE, findings = "missing R/principal_graph_pseudotime.R"))
  }
  if (file.info(module)$size > 131072) {
    findings <- c(findings, "candidate module exceeds 128 KiB")
  }
  text <- paste(readLines(module, warn = FALSE), collapse = "\n")
  if (!grepl("PrincipalGraphPseudotime\\s*<-\\s*function\\s*\\(", text, perl = TRUE)) {
    findings <- c(findings, "missing required PrincipalGraphPseudotime function")
  }
  forbidden <- c(
    "downstream package name" = "monocle",
    "package/source loading" = "library\\s*\\(|require(?:Namespace)?\\s*\\(|source\\s*\\(",
    "process execution" = "system2?\\s*\\(|pipe\\s*\\(|fifo\\s*\\(",
    "network or URL access" = "socket|download\\.file|url\\s*\\(|curl|wget|https?://",
    "native or foreign escape" = "dyn\\.load|(?<![a-z0-9_])\\.call\\s*\\(|(?<![a-z0-9_])\\.c\\s*\\(|reticulate",
    "hidden path access" = "/tests|/opt/|/solution|/public-cases",
    "dynamic code or environment" = "Sys\\.getenv|eval\\s*\\(|parse\\s*\\(|getFromNamespace"
  )
  lowered <- tolower(text)
  for (label in names(forbidden)) {
    if (grepl(forbidden[[label]], lowered, perl = TRUE)) {
      findings <- c(findings, paste("forbidden", label))
    }
  }

  namespace <- readLines(file.path(candidate_root, "NAMESPACE"), warn = FALSE)
  pristine_namespace <- readLines(file.path(pristine_root, "NAMESPACE"), warn = FALSE)
  export_line <- "export(PrincipalGraphPseudotime)"
  stripped_namespace <- namespace[namespace != export_line]
  if (sum(namespace == export_line) != 1L || !identical(stripped_namespace, pristine_namespace)) {
    findings <- c(findings, "NAMESPACE must add exactly export(PrincipalGraphPseudotime)")
  }

  description <- readLines(file.path(candidate_root, "DESCRIPTION"), warn = FALSE)
  pristine_description <- readLines(file.path(pristine_root, "DESCRIPTION"), warn = FALSE)
  collate_line <- "    'principal_graph_pseudotime.R'"
  stripped_description <- description[description != collate_line]
  if (sum(description == collate_line) != 1L || !identical(stripped_description, pristine_description)) {
    findings <- c(findings, "DESCRIPTION must add exactly the principal graph Collate entry")
  }

  changed <- audit_original_tree(candidate_root, pristine_root)
  if (length(changed)) {
    preview <- paste(head(changed, 8L), collapse = ", ")
    findings <- c(findings, paste0("unrelated pristine files changed or removed: ", preview))
  }
  list(passed = length(findings) == 0L, findings = unname(findings))
}

geometry_map <- function(left_case, right_case) {
  left <- case_matrices(left_case)$embedding
  right <- case_matrices(right_case)$embedding
  vapply(seq_len(nrow(left)), function(index) {
    distances <- rowSums((right - matrix(
      left[index, ], nrow(right), ncol(right), byrow = TRUE
    ))^2)
    which.min(distances)
  }, integer(1))
}

metamorphic_check <- function(pair) {
  left <- run_pair(pair$left)
  right <- run_pair(pair$right)
  left_diff <- compare_outputs(left$reference, left$candidate)
  right_diff <- compare_outputs(right$reference, right$candidate)
  if (pair$kind == "same") {
    mapping <- seq_along(left$candidate$cell_names)
  } else {
    mapping <- geometry_map(pair$left, pair$right)
  }
  error <- Inf
  categorical_ok <- FALSE
  if (left_diff$passed && right_diff$passed &&
      identical(left$candidate$status, "ok") && identical(right$candidate$status, "ok")) {
    error <- max(abs(
      left$candidate$pseudotime - right$candidate$pseudotime[mapping]
    ))
    categorical_ok <-
      identical(left$candidate$closest_vertex, right$candidate$closest_vertex[mapping]) &&
      identical(left$candidate$cell_state, right$candidate$cell_state[mapping]) &&
      identical(left$candidate$vertex_role, right$candidate$vertex_role) &&
      identical(left$candidate$root_vertices, right$candidate$root_vertices)
  }
  list(
    name = pair$name,
    passed = left_diff$passed && right_diff$passed &&
      error <= PSEUDOTIME_TOL && categorical_ok,
    pseudotime_invariance_error = finite_or_null(error),
    categorical_fields_invariant = categorical_ok
  )
}

main <- function() {
  dir.create(LOG_DIR, recursive = TRUE, showWarnings = FALSE)
  report <- list(
    task = "algobridge-0003__seurat__absorbs__monocle",
    reference = "locked real Monocle3 1.4.26 project2MST plus order_cells",
    pseudotime_tolerance = PSEUDOTIME_TOL
  )
  reward <- 0
  tryCatch({
    audit <- source_audit()
    report$source_audit <- audit
    for (section_name in c("public", "hidden")) {
      cases <- if (section_name == "public") public_cases() else hidden_cases()
      rows <- lapply(cases, function(case) {
        values <- run_pair(case)
        comparison <- compare_outputs(values$reference, values$candidate)
        c(list(name = case$name, passed = comparison$passed), comparison$detail)
      })
      report[[section_name]] <- list(
        passed = sum(vapply(rows, function(row) isTRUE(row$passed), logical(1))),
        total = length(rows), cases = rows
      )
    }

    invalid_rows <- lapply(names(invalid_cases()), function(name) {
      values <- run_pair(invalid_cases()[[name]])
      passed <- identical(values$reference$status, "invalid_input") &&
        identical(values$candidate$status, "invalid_input")
      list(
        name = name, passed = passed,
        reference_status = values$reference$status,
        candidate_status = values$candidate$status
      )
    })
    report$invalid <- list(
      passed = sum(vapply(invalid_rows, function(row) isTRUE(row$passed), logical(1))),
      total = length(invalid_rows), cases = invalid_rows
    )

    meta_rows <- lapply(metamorphic_pairs(), metamorphic_check)
    report$metamorphic <- list(
      passed = sum(vapply(meta_rows, function(row) isTRUE(row$passed), logical(1))),
      total = length(meta_rows), cases = meta_rows
    )

    hidden_passed <- report$hidden$passed
    support_ok <- report$invalid$passed == report$invalid$total &&
      report$metamorphic$passed == report$metamorphic$total
    if (!support_ok && hidden_passed == report$hidden$total) {
      hidden_passed <- report$hidden$total - 1L
    }
    reward <- if (isTRUE(audit$passed)) hidden_passed / report$hidden$total else 0
    report$reward <- reward
    report$reward_rule <- paste(
      "hidden pass fraction; source audit gates to zero; incomplete invalid or",
      "metamorphic coverage caps an otherwise perfect score at 14/15"
    )
  }, error = function(error) {
    report$fatal_error <- conditionMessage(error)
    report$traceback <- paste(utils::capture.output(traceback()), collapse = "\n")
    report$reward <- 0
    reward <<- 0
  })
  write_json(
    report, file.path(LOG_DIR, "verifier_report.json"),
    auto_unbox = TRUE, pretty = TRUE, digits = 17, null = "null", na = "null"
  )
  writeLines(sprintf("%.12g", reward), file.path(LOG_DIR, "reward.txt"))
  cat(toJSON(report, auto_unbox = TRUE, pretty = TRUE, digits = 17,
             null = "null", na = "null"), "\n")
  invisible(0L)
}

main()
