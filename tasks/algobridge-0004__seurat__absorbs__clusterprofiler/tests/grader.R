#!/usr/bin/env Rscript

options(warn = 1, stringsAsFactors = FALSE)

TASK_ID <- "ALGOBRIDGE-0004"
TESTBED <- "/testbed"
TESTS <- "/tests"
PRISTINE <- "/opt/pristine-host"
REFERENCE_ROOT <- "/opt/reference"
REFERENCE_RUNNER <- "/opt/reference-runner/reference_runner.R"
CANDIDATE_RUNNER <- "/opt/candidate-runner/candidate_runner.R"
ARCHIVE_ROOT <- "/opt/source-archives"
LOG_ROOT <- "/logs/verifier"
EXPECTED_COLUMNS <- c(
  "term", "description", "overlap", "GeneRatio", "BgRatio",
  "pvalue", "p.adjust", "qvalue", "genes"
)
EXPECTED_FORMALS <- c(
  "markers", "TERM2GENE", "universe", "TERM2NAME", "minGSSize",
  "maxGSSize", "pvalueCutoff", "qvalueCutoff"
)

dir.create(LOG_ROOT, recursive = TRUE, showWarnings = FALSE)

json_string <- function(value) {
  if (length(value) != 1L || is.na(value)) return("null")
  encodeString(enc2utf8(as.character(value)), quote = '"', na.encode = FALSE)
}

json_encode <- function(value) {
  if (is.null(value)) return("null")
  if (is.list(value)) {
    if (length(value) == 0L) return("[]")
    named <- !is.null(names(value)) && all(nzchar(names(value)))
    encoded <- vapply(value, json_encode, character(1L), USE.NAMES = FALSE)
    if (named) {
      fields <- paste0(vapply(names(value), json_string, character(1L)), ":", encoded)
      return(paste0("{", paste(fields, collapse = ","), "}"))
    }
    return(paste0("[", paste(encoded, collapse = ","), "]"))
  }
  if (length(value) > 1L) {
    return(paste0(
      "[",
      paste(vapply(as.list(value), json_encode, character(1L)), collapse = ","),
      "]"
    ))
  }
  if (is.character(value)) return(json_string(value))
  if (is.logical(value)) {
    if (is.na(value)) return("null")
    return(if (value) "true" else "false")
  }
  if (is.numeric(value)) {
    if (is.na(value) || !is.finite(value)) return("null")
    return(format(value, digits = 17L, scientific = TRUE, trim = TRUE))
  }
  json_string(as.character(value))
}

write_report <- function(report, reward) {
  report$reward <- as.double(reward)
  writeLines(json_encode(report), file.path(LOG_ROOT, "report.json"), useBytes = TRUE)
  writeLines(format(as.double(reward), digits = 12L, scientific = FALSE, trim = TRUE),
             file.path(LOG_ROOT, "reward.txt"))
}

hard_fail <- function(reason, gates = list()) {
  report <- list(
    task_id = TASK_ID,
    status = "hard_gate_failed",
    reason = reason,
    hard_gates = gates,
    passed = 0L,
    total = 15L,
    cases = list()
  )
  write_report(report, 0)
  message(TASK_ID, " hard gate: ", reason)
  quit(save = "no", status = 0L)
}

sha256_file <- function(path) {
  output <- system2("sha256sum", path, stdout = TRUE, stderr = TRUE)
  status <- attr(output, "status")
  if (!is.null(status) && status != 0L) stop("sha256sum failed for ", path)
  digest <- sub("[[:space:]].*$", "", output[[1L]])
  if (!grepl("^[0-9a-f]{64}$", digest)) stop("invalid digest for ", path)
  digest
}

all_paths <- function(root) {
  list.files(
    root,
    recursive = TRUE,
    all.files = TRUE,
    full.names = TRUE,
    include.dirs = FALSE,
    no.. = TRUE
  )
}

relative_paths <- function(root) {
  paths <- all_paths(root)
  prefix <- paste0(sub("/+$", "", root), "/")
  stats::setNames(paths, substring(paths, nchar(prefix) + 1L))
}

manifest <- function(root) {
  paths <- relative_paths(root)
  output <- character(length(paths))
  names(output) <- names(paths)
  for (i in seq_along(paths)) {
    link <- Sys.readlink(paths[[i]])
    output[[i]] <- if (nzchar(link)) paste0("SYMLINK:", link) else sha256_file(paths[[i]])
  }
  output
}

read_text <- function(path) {
  paste(readLines(path, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
}

lexical_tokens <- function(text) {
  text <- gsub("#[^\n]*", " ", text, perl = TRUE)
  text <- gsub("\"(?:\\\\.|[^\"\\\\])*\"|'(?:\\\\.|[^'\\\\])*'", " ", text, perl = TRUE)
  pattern <- paste0(
    "[A-Za-z.][A-Za-z0-9._]*|",
    "(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?|",
    "<-|->|<=|>=|==|!=|&&|\\|\\||%[^%]*%|[+*/^$@:[\\](){},;=-]"
  )
  hit <- gregexpr(pattern, text, perl = TRUE)
  regmatches(text, hit)[[1L]]
}

donor_fragments <- function() {
  paths <- c(
    file.path(REFERENCE_ROOT, "clusterProfiler/R/enricher.R"),
    file.path(REFERENCE_ROOT, "DOSE/R/build_Anno.R"),
    file.path(REFERENCE_ROOT, "DOSE/R/enricher_internal.R"),
    file.path(REFERENCE_ROOT, "qvalue/R/qvalue.R"),
    file.path(REFERENCE_ROOT, "qvalue/R/pi0est.R")
  )
  fragments <- new.env(hash = TRUE, parent = emptyenv())
  for (path in paths) {
    tokens <- lexical_tokens(read_text(path))
    for (width in c(64L, 96L)) {
      if (length(tokens) >= width) {
        for (start in seq_len(length(tokens) - width + 1L)) {
          key <- paste(tokens[start:(start + width - 1L)], collapse = "\037")
          assign(paste0(width, ":", key), TRUE, envir = fragments)
        }
      }
    }
  }
  fragments
}

source_policy <- function(fragments) {
  pristine <- manifest(PRISTINE)
  candidate <- manifest(TESTBED)
  pristine_names <- names(pristine)
  candidate_names <- names(candidate)
  missing <- setdiff(pristine_names, candidate_names)
  added <- sort(setdiff(candidate_names, pristine_names), method = "radix")
  shared <- intersect(pristine_names, candidate_names)
  changed <- sort(shared[pristine[shared] != candidate[shared]], method = "radix")

  if (length(missing)) return(list(ok = FALSE, detail = paste("removed host files:", paste(head(missing, 5L), collapse = ", "))))
  if (!identical(added, "R/enrichment.R")) {
    if (length(added) == 0L) return(list(ok = FALSE, detail = "R/enrichment.R was not added"))
    return(list(ok = FALSE, detail = paste("unexpected added files:", paste(head(added, 8L), collapse = ", "))))
  }
  if (!identical(changed, "NAMESPACE")) {
    if (length(changed) == 0L) return(list(ok = FALSE, detail = "NAMESPACE export was not added"))
    return(list(ok = FALSE, detail = paste("unexpected changed files:", paste(head(changed, 8L), collapse = ", "))))
  }

  implementation <- file.path(TESTBED, "R/enrichment.R")
  link <- Sys.readlink(implementation)
  size <- file.info(implementation)$size
  if (nzchar(link) || is.na(size) || size < 1500L || size > 60000L) {
    return(list(ok = FALSE, detail = "R/enrichment.R is linked or outside the size bound"))
  }
  parse_error <- tryCatch({ parse(file = implementation); NULL }, error = identity)
  if (!is.null(parse_error)) {
    return(list(ok = FALSE, detail = paste("R parse failure:", conditionMessage(parse_error))))
  }

  pristine_namespace <- readLines(file.path(PRISTINE, "NAMESPACE"), warn = FALSE)
  candidate_namespace <- readLines(file.path(TESTBED, "NAMESPACE"), warn = FALSE)
  export_line <- candidate_namespace == "export(EnrichMarkers)"
  if (sum(export_line) != 1L || !identical(candidate_namespace[!export_line], pristine_namespace)) {
    return(list(ok = FALSE, detail = "NAMESPACE must contain only one added EnrichMarkers export"))
  }

  text <- read_text(implementation)
  forbidden <- paste0(
    "(?i)(clusterprofiler|\\bDOSE\\b|qvalue[[:space:]]*::|::|",
    "\\b(?:library|require|requireNamespace|source|sys\\.source|system|system2|shell|",
    "pipe|fifo|socketConnection|url|download\\.file|dyn\\.load|readLines|readRDS|load|",
    "Sys\\.getenv|Sys\\.setenv)\\s*\\(|/opt/|/tests(?:/|\\b)|reference[_-])"
  )
  match <- regexpr(forbidden, text, perl = TRUE)
  if (match[[1L]] != -1L) {
    token <- regmatches(text, match)
    return(list(ok = FALSE, detail = paste0("forbidden dependency/execution token: ", token)))
  }

  tokens <- lexical_tokens(text)
  for (width in c(96L, 64L)) {
    if (length(tokens) >= width) {
      for (start in seq_len(length(tokens) - width + 1L)) {
        key <- paste0(width, ":", paste(tokens[start:(start + width - 1L)], collapse = "\037"))
        if (exists(key, envir = fragments, inherits = FALSE)) {
          return(list(ok = FALSE, detail = paste0("normalized donor fragment detected (", width, " tokens)")))
        }
      }
    }
  }

  list(
    ok = TRUE,
    detail = list(
      added = added,
      changed = changed,
      implementation_sha256 = sha256_file(implementation),
      implementation_bytes = as.integer(size),
      donor_fragment_scan = "pass (64/96 lexical tokens)"
    )
  )
}

reference_integrity <- function() {
  expected_archives <- c(
    "host-source.tar.gz" = "afa95adc7012df50fe7c63bc744eb44dd72e241929b9180a1bc6b53d050601ae",
    "clusterprofiler-source.tar.gz" = "814bdb801534badf75c6efe8ff623cc7d2279e478055736aef4efbc6b593e324",
    "dose-source.tar.gz" = "94f09d7247b7c9c4f34475e984b87350d778eb1983e8240b7d575c6fedbb1f0b",
    "qvalue-source.tar.gz" = "569faa5c3757931d54159073764765cea532dd1a6faef9f832377b9a30d3b2c5"
  )
  findings <- character()
  for (name in names(expected_archives)) {
    path <- file.path(ARCHIVE_ROOT, name)
    if (!file.exists(path) || !identical(sha256_file(path), expected_archives[[name]])) {
      findings <- c(findings, paste("archive identity failed:", name))
    }
  }
  required <- c(
    file.path(PRISTINE, "DESCRIPTION"),
    file.path(PRISTINE, "NAMESPACE"),
    file.path(REFERENCE_ROOT, "clusterProfiler/R/enricher.R"),
    file.path(REFERENCE_ROOT, "DOSE/R/enricher_internal.R"),
    file.path(REFERENCE_ROOT, "qvalue/R/qvalue.R"),
    REFERENCE_RUNNER,
    CANDIDATE_RUNNER
  )
  missing_required <- required[!file.exists(required)]
  if (length(missing_required)) {
    findings <- c(findings, paste("missing locked file:", missing_required))
  }
  if (length(manifest(PRISTINE)) != 430L) findings <- c(findings, "pristine host file count is not 430")
  if (!any(grepl("^Version: 5.3.1$", readLines(file.path(PRISTINE, "DESCRIPTION")), fixed = FALSE))) {
    findings <- c(findings, "Seurat version identity failed")
  }
  if (!identical(paste(R.version$major, R.version$minor, sep = "."), "4.5.1")) {
    findings <- c(findings, paste("unexpected R version:", R.version.string))
  }
  lock_text <- read_text(file.path(TESTS, "source-lock.json"))
  commits <- c(
    "ca0ab0f9dd6863fac4a6af87280d48c8f9cc9b95",
    "0f8dd3d779918e9fbcdd42aa726f634fa93a6a03",
    "eb8781d71676625aaca21d072968531335a39ab0",
    "09da9f467ca4d8bddd2dbe82ba12401fcbbb2a65"
  )
  if (!all(vapply(commits, grepl, logical(1L), x = lock_text, fixed = TRUE))) {
    findings <- c(findings, "source lock commit identity failed")
  }
  findings
}

run_program <- function(command, args, stdout_path, stderr_path) {
  status <- system2(command, args, stdout = stdout_path, stderr = stderr_path)
  if (is.null(status)) 0L else as.integer(status)
}

destroy_reference_material <- function() {
  targets <- c(REFERENCE_ROOT, PRISTINE, "/opt/reference-runner", ARCHIVE_ROOT)
  for (target in targets) unlink(target, recursive = TRUE, force = TRUE)
  remaining <- targets[file.exists(targets)]
  if (length(remaining)) stop("reference cleanup failed: ", paste(remaining, collapse = ", "))
  packages <- c("clusterProfiler", "DOSE", "qvalue")
  installed <- vapply(packages, requireNamespace, logical(1L), quietly = TRUE)
  if (any(installed)) stop("forbidden reference package remains installed: ", paste(packages[installed], collapse = ", "))
  TRUE
}

validate_candidate_table <- function(value) {
  if (!is.data.frame(value)) return("result is not a data.frame")
  if (!identical(names(value), EXPECTED_COLUMNS)) return("result columns or order are invalid")
  n <- nrow(value)
  character_columns <- c("term", "description", "GeneRatio", "BgRatio", "genes")
  if (!all(vapply(value[character_columns], is.character, logical(1L)))) return("string columns must be character")
  if (!is.integer(value$overlap)) return("overlap must be integer")
  if (!all(vapply(value[c("pvalue", "p.adjust", "qvalue")], is.double, logical(1L)))) {
    return("probability columns must be double")
  }
  if (anyNA(value[character_columns]) || anyNA(value$overlap)) return("non-qvalue columns contain NA")
  if (anyDuplicated(value$term)) return("term IDs are duplicated")
  if (any(!is.finite(value$pvalue)) || any(!is.finite(value$p.adjust))) return("p-values are not finite")
  if (any(value$pvalue < 0 | value$pvalue > 1) || any(value$p.adjust < 0 | value$p.adjust > 1)) {
    return("p-values are outside [0,1]")
  }
  if (anyNA(value$qvalue) && !all(is.na(value$qvalue))) return("qvalue must be wholly present or wholly NA")
  present_q <- value$qvalue[!is.na(value$qvalue)]
  if (any(!is.finite(present_q)) || any(present_q < 0 | present_q > 1)) return("q-values are invalid")
  if (any(value$p.adjust + 2e-12 < value$pvalue)) return("BH adjusted p is smaller than raw p")
  if (n > 1L) {
    expected_order <- order(value$pvalue, value$term, method = "radix")
    if (!identical(expected_order, seq_len(n))) return("rows are not canonically ordered")
  }
  ratio_pattern <- "^[0-9]+/[0-9]+$"
  if (any(!grepl(ratio_pattern, value$GeneRatio)) || any(!grepl(ratio_pattern, value$BgRatio))) {
    return("ratio formatting is invalid")
  }
  for (i in seq_len(n)) {
    gene_hits <- if (nzchar(value$genes[[i]])) strsplit(value$genes[[i]], "/", fixed = TRUE)[[1L]] else character()
    if (length(gene_hits) != value$overlap[[i]] || anyDuplicated(gene_hits) ||
        !identical(gene_hits, sort(gene_hits, method = "radix"))) {
      return(paste("hit-gene set is invalid for term", value$term[[i]]))
    }
    numerator <- as.integer(strsplit(value$GeneRatio[[i]], "/", fixed = TRUE)[[1L]][[1L]])
    if (!identical(numerator, value$overlap[[i]])) return("GeneRatio numerator does not match overlap")
  }
  NULL
}

numeric_close <- function(actual, expected) {
  if (!identical(is.na(actual), is.na(expected))) return(FALSE)
  index <- !is.na(expected)
  if (!any(index)) return(TRUE)
  error <- abs(actual[index] - expected[index])
  all(error <= 1e-12 | error <= 1e-12 * pmax(abs(expected[index]), .Machine$double.xmin))
}

compare_case <- function(actual, expected) {
  issue <- validate_candidate_table(actual)
  if (!is.null(issue)) return(list(pass = FALSE, detail = issue))
  if (nrow(actual) != nrow(expected)) {
    return(list(pass = FALSE, detail = paste("row count", nrow(actual), "!=", nrow(expected))))
  }
  exact_columns <- c("term", "description", "overlap", "GeneRatio", "BgRatio", "genes")
  for (name in exact_columns) {
    if (!identical(actual[[name]], expected[[name]])) {
      return(list(pass = FALSE, detail = paste("exact column mismatch:", name)))
    }
  }
  numeric_columns <- c("pvalue", "p.adjust", "qvalue")
  for (name in numeric_columns) {
    if (!numeric_close(actual[[name]], expected[[name]])) {
      difference <- suppressWarnings(max(abs(actual[[name]] - expected[[name]]), na.rm = TRUE))
      if (!is.finite(difference)) difference <- NA_real_
      return(list(pass = FALSE, detail = paste("numeric column mismatch:", name), max_error = difference))
    }
  }
  maximums <- lapply(numeric_columns, function(name) {
    difference <- suppressWarnings(max(abs(actual[[name]] - expected[[name]]), na.rm = TRUE))
    if (is.finite(difference)) difference else 0
  })
  names(maximums) <- numeric_columns
  list(pass = TRUE, detail = "match", max_errors = maximums)
}

source(file.path(TESTS, "cases.R"), local = globalenv())
gates <- list()

integrity_findings <- tryCatch(reference_integrity(), error = function(error) conditionMessage(error))
if (length(integrity_findings)) hard_fail(paste(integrity_findings, collapse = "; "), gates)
gates$reference_integrity <- "pass"

fragments <- tryCatch(donor_fragments(), error = function(error) hard_fail(conditionMessage(error), gates))
policy <- tryCatch(source_policy(fragments), error = function(error) list(ok = FALSE, detail = conditionMessage(error)))
if (!isTRUE(policy$ok)) hard_fail(policy$detail, gates)
gates$source_policy <- policy$detail

hidden <- hidden_cases()
invalid <- invalid_cases()
reference_input <- "/tmp/reference-input.rds"
reference_output <- "/tmp/reference-output.rds"
saveRDS(hidden, reference_input, version = 3L)
reference_stdout <- "/tmp/reference.stdout"
reference_stderr <- "/tmp/reference.stderr"
reference_status <- run_program(
  "Rscript",
  c(REFERENCE_RUNNER, reference_input, reference_output),
  reference_stdout,
  reference_stderr
)
if (reference_status != 0L || !file.exists(reference_output)) {
  hard_fail(paste("locked reference failed with status", reference_status), gates)
}
reference_results <- readRDS(reference_output)
if (length(reference_results) != length(hidden) ||
    any(!vapply(reference_results, function(x) isTRUE(x$ok), logical(1L)))) {
  hard_fail("locked reference did not produce all hidden outputs", gates)
}
expected <- lapply(reference_results, `[[`, "value")
gates$real_reference <- list(
  status = "pass",
  entry_point = "locked clusterProfiler::enricher source",
  hidden_outputs = length(expected)
)

unlink(c(reference_input, reference_output, reference_stdout, reference_stderr), force = TRUE)
cleanup_ok <- tryCatch(destroy_reference_material(), error = function(error) conditionMessage(error))
if (!isTRUE(cleanup_ok)) hard_fail(as.character(cleanup_ok), gates)
gates$reference_removed <- "pass"

candidate_write_before <- system2(
  "runuser",
  c("-u", "candidate", "--", "test", "-w", TESTBED),
  stdout = FALSE,
  stderr = FALSE
)
if (identical(as.integer(candidate_write_before), 0L)) {
  readonly_status <- system2("chmod", c("-R", "a-w", TESTBED), stdout = FALSE, stderr = FALSE)
  if (!identical(as.integer(readonly_status), 0L)) {
    hard_fail("unable to make /testbed read-only for candidate execution", gates)
  }
}

candidate_work <- "/tmp/candidate-work"
candidate_home <- "/tmp/candidate-home"
dir.create(candidate_work, recursive = TRUE, showWarnings = FALSE, mode = "0777")
dir.create(candidate_home, recursive = TRUE, showWarnings = FALSE, mode = "0777")
Sys.chmod(c(candidate_work, candidate_home), mode = "0777", use_umask = FALSE)

candidate_input <- file.path(candidate_work, "input.rds")
candidate_output <- file.path(candidate_work, "output.rds")
candidate_stdout <- file.path(candidate_work, "stdout.log")
candidate_stderr <- file.path(candidate_work, "stderr.log")
all_cases <- c(hidden, invalid)
saveRDS(all_cases, candidate_input, version = 3L)
Sys.chmod(candidate_input, mode = "0444")

write_check <- system2(
  "runuser",
  c("-u", "candidate", "--", "sh", "-c", shQuote("test ! -w /testbed && test ! -r /tests/grader.R")),
  stdout = FALSE,
  stderr = FALSE
)
if (!identical(as.integer(write_check), 0L)) hard_fail("candidate filesystem isolation check failed", gates)

candidate_status <- run_program(
  "/usr/bin/timeout",
  c(
    "180", "runuser", "-u", "candidate", "--", "env",
    "HOME=/tmp/candidate-home", "R_ENVIRON_USER=/dev/null", "R_PROFILE_USER=/dev/null",
    "R_LIBS_USER=/nonexistent", "R_DISABLE_INTERNET=1",
    "Rscript", CANDIDATE_RUNNER, candidate_input, candidate_output
  ),
  candidate_stdout,
  candidate_stderr
)
if (candidate_status != 0L || !file.exists(candidate_output)) {
  stderr_tail <- if (file.exists(candidate_stderr)) {
    paste(tail(readLines(candidate_stderr, warn = FALSE), 8L), collapse = " | ")
  } else {
    "no stderr"
  }
  hard_fail(paste("candidate runner failed with status", candidate_status, "-", stderr_tail), gates)
}
output_size <- file.info(candidate_output)$size
if (is.na(output_size) || output_size > 10 * 1024 * 1024) hard_fail("candidate output is too large", gates)
candidate_results <- tryCatch(readRDS(candidate_output), error = function(error) hard_fail("candidate output is not valid RDS", gates))
if (!is.list(candidate_results) || length(candidate_results) != length(all_cases)) {
  hard_fail("candidate output has the wrong result count", gates)
}

invalid_results <- candidate_results[(length(hidden) + 1L):length(all_cases)]
invalid_pass <- vapply(invalid_results, function(x) is.list(x) && identical(x$ok, FALSE), logical(1L))
if (!all(invalid_pass)) {
  failed_names <- vapply(invalid[!invalid_pass], `[[`, character(1L), "name")
  hard_fail(paste("malformed inputs were accepted:", paste(failed_names, collapse = ", ")), gates)
}
gates$invalid_inputs <- list(status = "pass", passed = length(invalid), total = length(invalid))
gates$candidate_isolation <- list(
  status = "pass",
  uid = 10001L,
  testbed = "read-only to candidate",
  tests = "unreadable to candidate",
  donor_packages = "absent",
  network = "disabled by Harbor"
)

case_reports <- vector("list", length(hidden))
passed <- 0L
for (i in seq_along(hidden)) {
  candidate_result <- candidate_results[[i]]
  if (!is.list(candidate_result) || !isTRUE(candidate_result$ok)) {
    detail <- if (is.list(candidate_result) && is.character(candidate_result$error)) candidate_result$error else "candidate error"
    comparison <- list(pass = FALSE, detail = detail)
  } else {
    comparison <- compare_case(candidate_result$value, expected[[i]])
  }
  if (isTRUE(comparison$pass)) passed <- passed + 1L
  case_reports[[i]] <- c(
    list(name = hidden[[i]]$name, pass = isTRUE(comparison$pass)),
    comparison[setdiff(names(comparison), "pass")]
  )
}

reward <- passed / length(hidden)
report <- list(
  task_id = TASK_ID,
  status = if (passed == length(hidden)) "accepted" else "scored",
  hard_gates = gates,
  passed = passed,
  total = length(hidden),
  cases = case_reports
)
write_report(report, reward)
message(TASK_ID, ": ", passed, "/", length(hidden), ", reward=", format(reward, digits = 6L))
