#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, warn = 1)

TASK_ID <- "ALGOBRIDGE-0005"
TESTBED <- "/testbed"
TESTS <- "/tests"
PRISTINE <- "/opt/pristine-host"
REFERENCE_ROOT <- "/opt/reference"
REFERENCE_RUNNER <- "/opt/reference-runner/reference_runner.R"
CANDIDATE_RUNNER <- "/opt/candidate-runner/candidate_runner.R"
ARCHIVE_ROOT <- "/opt/source-archives"
LOG_ROOT <- "/logs/verifier"
EXPECTED_FIELDS <- c(
  "logCPM", "weights", "coefficients", "contrast.coefficients",
  "t", "p.value", "df.total", "norm.factors"
)
TOLERANCES <- list(
  logCPM = c(abs = 5e-10, rel = 5e-10),
  weights = c(abs = 2e-7, rel = 5e-8),
  coefficients = c(abs = 2e-8, rel = 2e-8),
  contrast.coefficients = c(abs = 2e-8, rel = 2e-8),
  t = c(abs = 2e-6, rel = 2e-7),
  p.value = c(abs = 2e-8, rel = 2e-6),
  df.total = c(abs = 2e-8, rel = 2e-8),
  norm.factors = c(abs = 5e-10, rel = 5e-10)
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
  writeLines(
    format(as.double(reward), digits = 12L, scientific = FALSE, trim = TRUE),
    file.path(LOG_ROOT, "reward.txt")
  )
}

hard_fail <- function(reason, gates = list()) {
  write_report(
    list(
      task_id = TASK_ID,
      status = "hard_gate_failed",
      reason = reason,
      hard_gates = gates,
      hidden = list(passed = 0L, total = 15L),
      public = list(passed = 0L, total = 5L),
      cases = list()
    ),
    0
  )
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
    file.path(REFERENCE_ROOT, "limma/R/voom.R"),
    file.path(REFERENCE_ROOT, "limma/R/lmfit.R"),
    file.path(REFERENCE_ROOT, "limma/R/contrasts.R"),
    file.path(REFERENCE_ROOT, "limma/R/fitFDist.R"),
    file.path(REFERENCE_ROOT, "limma/R/squeezeVar.R"),
    file.path(REFERENCE_ROOT, "limma/R/ebayes.R"),
    file.path(REFERENCE_ROOT, "statmod/R/digamma.R")
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
  missing <- sort(setdiff(pristine_names, candidate_names), method = "radix")
  added <- sort(setdiff(candidate_names, pristine_names), method = "radix")
  shared <- intersect(pristine_names, candidate_names)
  changed <- sort(shared[pristine[shared] != candidate[shared]], method = "radix")

  if (length(missing)) {
    return(list(ok = FALSE, detail = paste("removed host files:", paste(head(missing, 6L), collapse = ", "))))
  }
  if (!identical(added, "R/voomFit.R")) {
    if (!length(added)) return(list(ok = FALSE, detail = "R/voomFit.R was not added"))
    return(list(ok = FALSE, detail = paste("unexpected added files:", paste(head(added, 8L), collapse = ", "))))
  }
  if (!identical(changed, "NAMESPACE")) {
    if (!length(changed)) return(list(ok = FALSE, detail = "NAMESPACE export was not added"))
    return(list(ok = FALSE, detail = paste("unexpected changed files:", paste(head(changed, 8L), collapse = ", "))))
  }

  implementation <- file.path(TESTBED, "R/voomFit.R")
  link <- Sys.readlink(implementation)
  size <- file.info(implementation)$size
  if (nzchar(link) || is.na(size) || size < 4500L || size > 80000L) {
    return(list(ok = FALSE, detail = "R/voomFit.R is linked or outside the size bound"))
  }
  parse_error <- tryCatch({ parse(file = implementation); NULL }, error = identity)
  if (!is.null(parse_error)) {
    return(list(ok = FALSE, detail = paste("R parse failure:", conditionMessage(parse_error))))
  }

  pristine_namespace <- readLines(file.path(PRISTINE, "NAMESPACE"), warn = FALSE)
  candidate_namespace <- readLines(file.path(TESTBED, "NAMESPACE"), warn = FALSE)
  export_line <- candidate_namespace == "export(voomFit)"
  if (sum(export_line) != 1L || !identical(candidate_namespace[!export_line], pristine_namespace)) {
    return(list(ok = FALSE, detail = "NAMESPACE must contain only one added voomFit export"))
  }

  text <- read_text(implementation)
  forbidden <- paste0(
    "(?i)(\\blimma\\b|\\bstatmod\\b|::|",
    "\\b(?:library|require|requireNamespace|source|sys\\.source|system|system2|shell|",
    "pipe|fifo|socketConnection|url|download\\.file|dyn\\.load|readLines|readRDS|load|",
    "Sys\\.getenv|Sys\\.setenv|file|gzfile|unz|serialize|unserialize)\\s*\\(|",
    "/opt/|/tests(?:/|\\b)|reference[_-])"
  )
  match <- regexpr(forbidden, text, perl = TRUE)
  if (match[[1L]] != -1L) {
    return(list(ok = FALSE, detail = paste0("forbidden dependency/execution token: ", regmatches(text, match))))
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
      donor_fragment_scan = "pass (64/96 lexical tokens)",
      unchanged_host_files = length(shared) - length(changed)
    )
  )
}

reference_integrity <- function() {
  expected_archives <- c(
    "host-source.tar.gz" = "744ed24f9a1c4ef6d77bd173511285cca04c58e7b7be4504ed8572e86e403f3a",
    "donor-source.tar.gz" = "f1a83f45a5bb68873385e0e415a15131ad1f65c78fa6fd53911c812bf41e76ff",
    "statmod-source.tar.gz" = "37bf14b86a068336e28970c5ce5282b2573a7ce4bdf4b8d8f6d3d5a492c7fe55"
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
    file.path(PRISTINE, "R/calcNormFactors.R"),
    file.path(REFERENCE_ROOT, "limma/DESCRIPTION"),
    file.path(REFERENCE_ROOT, "limma/R/voom.R"),
    file.path(REFERENCE_ROOT, "limma/R/lmfit.R"),
    file.path(REFERENCE_ROOT, "limma/R/ebayes.R"),
    file.path(REFERENCE_ROOT, "statmod/R/digamma.R"),
    REFERENCE_RUNNER,
    CANDIDATE_RUNNER
  )
  missing_required <- required[!file.exists(required)]
  if (length(missing_required)) findings <- c(findings, paste("missing locked file:", missing_required))
  if (length(manifest(PRISTINE)) != 252L) findings <- c(findings, "pristine edgeR file count is not 252")
  if (length(manifest(file.path(REFERENCE_ROOT, "limma"))) != 291L) findings <- c(findings, "limma file count is not 291")
  if (length(manifest(file.path(REFERENCE_ROOT, "statmod"))) != 63L) findings <- c(findings, "statmod file count is not 63")

  version_of <- function(path) read.dcf(path, fields = "Version")[[1L]]
  if (!identical(version_of(file.path(PRISTINE, "DESCRIPTION")), "4.6.3")) findings <- c(findings, "edgeR version identity failed")
  if (!identical(version_of(file.path(REFERENCE_ROOT, "limma/DESCRIPTION")), "3.64.3")) findings <- c(findings, "limma version identity failed")
  if (!identical(version_of(file.path(REFERENCE_ROOT, "statmod/DESCRIPTION")), "1.5.0")) findings <- c(findings, "statmod version identity failed")
  if (!identical(paste(R.version$major, R.version$minor, sep = "."), "4.5.1")) {
    findings <- c(findings, paste("unexpected R version:", R.version.string))
  }
  lock_text <- read_text(file.path(TESTS, "source-lock.json"))
  commits <- c(
    "0dc836a7c8e53633bb7817d55b27128ceb898ac9",
    "0f42428e09766efb49ab672419cdbe745872b22e",
    "f85e32011346fb75d2b967cf2aff1f2e01a10ba8"
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
  packages <- c("limma", "statmod")
  installed <- vapply(packages, requireNamespace, logical(1L), quietly = TRUE)
  if (any(installed)) stop("forbidden donor package remains installed: ", paste(packages[installed], collapse = ", "))
  TRUE
}

validate_candidate_value <- function(value, case) {
  if (!is.list(value) || !identical(names(value), EXPECTED_FIELDS)) {
    return("result must be a list with the exact required fields and order")
  }
  genes <- nrow(case$counts)
  samples <- ncol(case$counts)
  terms <- ncol(case$design)
  matrix_dims <- list(
    logCPM = c(genes, samples),
    weights = c(genes, samples),
    coefficients = c(genes, terms)
  )
  for (name in names(matrix_dims)) {
    item <- value[[name]]
    if (!is.matrix(item) || !is.double(item) || !identical(dim(item), matrix_dims[[name]])) {
      return(paste(name, "has invalid type or dimensions"))
    }
    if (any(!is.finite(item))) return(paste(name, "contains non-finite values"))
  }
  vectors <- c("contrast.coefficients", "t", "p.value", "df.total")
  for (name in vectors) {
    item <- value[[name]]
    if (!is.double(item) || !is.null(dim(item)) || length(item) != genes || any(!is.finite(item))) {
      return(paste(name, "has invalid type, length, or values"))
    }
  }
  nf <- value$norm.factors
  if (!is.double(nf) || !is.null(dim(nf)) || length(nf) != samples || any(!is.finite(nf))) {
    return("norm.factors has invalid type, length, or values")
  }
  if (any(value$weights <= 0)) return("weights must be positive")
  if (any(value$p.value < 0 | value$p.value > 1)) return("p.value is outside [0,1]")
  if (any(value$df.total <= 0)) return("df.total must be positive")
  if (any(nf <= 0) || abs(sum(log(nf))) > 1e-8) return("normalization factors are invalid")
  NULL
}

numeric_close <- function(actual, expected, tolerance) {
  if (!identical(dim(actual), dim(expected)) || !identical(length(actual), length(expected))) return(FALSE)
  if (!identical(is.na(actual), is.na(expected))) return(FALSE)
  index <- !is.na(expected)
  if (!any(index)) return(TRUE)
  difference <- abs(actual[index] - expected[index])
  all(difference <= tolerance[["abs"]] + tolerance[["rel"]] * pmax(abs(expected[index]), .Machine$double.xmin))
}

maximum_error <- function(actual, expected) {
  value <- suppressWarnings(max(abs(actual - expected), na.rm = TRUE))
  if (is.finite(value)) value else NA_real_
}

compare_case <- function(actual, expected, case) {
  issue <- validate_candidate_value(actual, case)
  if (!is.null(issue)) return(list(pass = FALSE, detail = issue))
  errors <- list()
  for (name in EXPECTED_FIELDS) {
    errors[[name]] <- maximum_error(actual[[name]], expected[[name]])
    if (!numeric_close(actual[[name]], expected[[name]], TOLERANCES[[name]])) {
      return(list(
        pass = FALSE,
        detail = paste("numeric mismatch:", name),
        max_error = errors[[name]]
      ))
    }
  }
  list(pass = TRUE, detail = "match", max_errors = errors)
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
gates$legacy_host_parity <- list(
  status = "pass",
  evidence = "all 252 locked host files preserved except the one-line NAMESPACE export; only R/voomFit.R added"
)

public <- public_cases()
hidden <- hidden_cases()
invalid <- invalid_cases()
all_valid <- c(public, hidden)
reference_input <- "/tmp/reference-input.rds"
reference_output_one <- "/tmp/reference-output-one.rds"
reference_output_two <- "/tmp/reference-output-two.rds"
saveRDS(all_valid, reference_input, version = 3L)

run_reference <- function(output, suffix) {
  stdout <- paste0("/tmp/reference-", suffix, ".stdout")
  stderr <- paste0("/tmp/reference-", suffix, ".stderr")
  status <- run_program("Rscript", c(REFERENCE_RUNNER, reference_input, output), stdout, stderr)
  if (status != 0L || !file.exists(output)) {
    hard_fail(paste("locked reference failed on", suffix, "with status", status), gates)
  }
  readRDS(output)
}

reference_one <- run_reference(reference_output_one, "one")
reference_two <- run_reference(reference_output_two, "two")
if (!identical(reference_one, reference_two)) hard_fail("locked reference is not deterministic", gates)
if (length(reference_one) != length(all_valid) ||
    any(!vapply(reference_one, function(x) isTRUE(x$ok), logical(1L)))) {
  hard_fail("locked reference did not produce all public and hidden outputs", gates)
}
expected <- lapply(reference_one, `[[`, "value")
gates$real_reference <- list(
  status = "pass",
  entry_points = "edgeR::calcNormFactors.default -> limma::voom -> lmFit -> contrasts.fit -> eBayes",
  runtime_outputs = length(expected),
  deterministic_replays = 2L
)

cleanup_ok <- tryCatch(destroy_reference_material(), error = function(error) conditionMessage(error))
if (!isTRUE(cleanup_ok)) hard_fail(as.character(cleanup_ok), gates)
gates$reference_removed <- "pass"

if (file.access(file.path(TESTS, "cases.R"), mode = 4L) != 0L) {
  hard_fail("verifier root unexpectedly cannot read its tests", gates)
}
candidate_test_read <- run_program(
  "runuser",
  c("-u", "candidate", "--", "test", "-r", file.path(TESTS, "cases.R")),
  "/tmp/test-read.stdout",
  "/tmp/test-read.stderr"
)
if (candidate_test_read == 0L) hard_fail("candidate user can read hidden verifier files", gates)

# Harbor restores the Agent artifact with provider-dependent ownership. Freeze
# regular files first, then directories from deepest to shallowest, so this is
# safe both for Docker-owned volumes and rootless bind mounts.
testbed_files <- all_paths(TESTBED)
file_permissions <- Sys.chmod(testbed_files, mode = "0444", use_umask = FALSE)
testbed_directories <- list.dirs(TESTBED, recursive = TRUE, full.names = TRUE)
testbed_directories <- testbed_directories[order(nchar(testbed_directories), decreasing = TRUE)]
directory_permissions <- Sys.chmod(testbed_directories, mode = "0555", use_umask = FALSE)
if (!all(file_permissions) || !all(directory_permissions)) {
  hard_fail("could not freeze the restored candidate artifact", gates)
}
candidate_test_write <- run_program(
  "runuser",
  c("-u", "candidate", "--", "test", "-w", TESTBED),
  "/tmp/test-write.stdout",
  "/tmp/test-write.stderr"
)
if (candidate_test_write == 0L) hard_fail("candidate user can write the testbed", gates)
writable_paths <- system2(
  "runuser",
  c("-u", "candidate", "--", "find", TESTBED, "-writable", "-print"),
  stdout = TRUE,
  stderr = TRUE
)
writable_status <- attr(writable_paths, "status")
if ((!is.null(writable_status) && writable_status != 0L) || length(writable_paths) != 0L) {
  hard_fail("candidate user has a writable path inside the testbed", gates)
}
gates$candidate_isolation <- list(
  status = "pass",
  uid = 10001L,
  verifier_tests_readable = FALSE,
  testbed_writable = FALSE,
  donor_packages_installed = FALSE,
  reference_paths_present = FALSE
)

candidate_before <- manifest(TESTBED)
candidate_work <- "/tmp/candidate-work"
dir.create(candidate_work, mode = "0700")
candidate_input <- file.path(candidate_work, "valid-input.rds")
candidate_output <- file.path(candidate_work, "valid-output.rds")
saveRDS(all_valid, candidate_input, version = 3L)
input_digest <- sha256_file(candidate_input)
chown_status <- system2("chown", c("-R", "10001:10001", candidate_work), stdout = FALSE, stderr = FALSE)
if (!is.null(chown_status) && chown_status != 0L) hard_fail("could not prepare candidate work directory", gates)

candidate_status <- run_program(
  "runuser",
  c(
    "-u", "candidate", "--", "env",
    "HOME=/tmp/candidate-home", "R_ENVIRON_USER=/dev/null", "R_PROFILE_USER=/dev/null",
    "Rscript", CANDIDATE_RUNNER, candidate_input, candidate_output
  ),
  "/tmp/candidate.stdout",
  "/tmp/candidate.stderr"
)
if (candidate_status != 0L || !file.exists(candidate_output)) {
  hard_fail(paste("candidate runner failed with status", candidate_status), gates)
}
if (!identical(sha256_file(candidate_input), input_digest)) hard_fail("candidate modified its valid input", gates)
candidate_after <- manifest(TESTBED)
if (!identical(candidate_before, candidate_after)) hard_fail("candidate modified the testbed during execution", gates)

candidate_results <- tryCatch(readRDS(candidate_output), error = identity)
if (inherits(candidate_results, "error") || length(candidate_results) != length(all_valid)) {
  hard_fail("candidate output is unreadable or has the wrong case count", gates)
}

invalid_input <- file.path(candidate_work, "invalid-input.rds")
invalid_output <- file.path(candidate_work, "invalid-output.rds")
saveRDS(invalid, invalid_input, version = 3L)
system2("chown", c("10001:10001", invalid_input), stdout = FALSE, stderr = FALSE)
invalid_status <- run_program(
  "runuser",
  c(
    "-u", "candidate", "--", "env",
    "HOME=/tmp/candidate-home", "R_ENVIRON_USER=/dev/null", "R_PROFILE_USER=/dev/null",
    "Rscript", CANDIDATE_RUNNER, invalid_input, invalid_output
  ),
  "/tmp/invalid.stdout",
  "/tmp/invalid.stderr"
)
if (invalid_status != 0L || !file.exists(invalid_output)) hard_fail("candidate invalid-input run failed", gates)
invalid_results <- tryCatch(readRDS(invalid_output), error = identity)
if (inherits(invalid_results, "error") || length(invalid_results) != length(invalid) ||
    any(vapply(invalid_results, function(x) isTRUE(x$ok), logical(1L)))) {
  hard_fail("candidate accepted malformed inputs", gates)
}
if (!identical(candidate_before, manifest(TESTBED))) hard_fail("candidate modified the testbed during invalid checks", gates)
gates$invalid_input_rejection <- list(status = "pass", rejected = length(invalid))

case_reports <- vector("list", length(all_valid))
passes <- logical(length(all_valid))
for (i in seq_along(all_valid)) {
  if (!isTRUE(candidate_results[[i]]$ok)) {
    comparison <- list(
      pass = FALSE,
      detail = paste("candidate error:", as.character(candidate_results[[i]]$error))
    )
  } else {
    comparison <- compare_case(candidate_results[[i]]$value, expected[[i]], all_valid[[i]])
  }
  passes[[i]] <- isTRUE(comparison$pass)
  case_reports[[i]] <- c(
    list(
      index = i,
      visibility = if (i <= length(public)) "public" else "hidden",
      name = all_valid[[i]]$name
    ),
    comparison
  )
}

public_passed <- sum(passes[seq_along(public)])
hidden_indices <- seq.int(length(public) + 1L, length(all_valid))
hidden_passed <- sum(passes[hidden_indices])
reward <- hidden_passed / length(hidden)
status <- if (hidden_passed == length(hidden) && public_passed == length(public)) "accepted" else "scored"
write_report(
  list(
    task_id = TASK_ID,
    status = status,
    hard_gates = gates,
    public = list(passed = public_passed, total = length(public)),
    hidden = list(passed = hidden_passed, total = length(hidden)),
    cases = case_reports
  ),
  reward
)
message(
  TASK_ID, " public ", public_passed, "/", length(public),
  ", hidden ", hidden_passed, "/", length(hidden),
  ", reward ", format(reward, digits = 6L)
)
