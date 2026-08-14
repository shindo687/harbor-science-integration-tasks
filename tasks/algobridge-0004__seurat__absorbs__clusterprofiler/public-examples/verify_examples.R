#!/usr/bin/env Rscript

source("/examples/public_cases.R", local = globalenv())
cases <- public_cases()
expected <- readRDS("/examples/expected.rds")
if (length(expected) != length(cases)) stop("public expected result count mismatch")

work <- tempfile("algobridge-0004-public-")
dir.create(work)
on.exit(unlink(work, recursive = TRUE, force = TRUE), add = TRUE)
input <- file.path(work, "input.rds")
output <- file.path(work, "output.rds")
saveRDS(cases, input, version = 3L)

status <- system2(
  "Rscript",
  c("/opt/task-tools/candidate_runner.R", input, output),
  stdout = "",
  stderr = ""
)
if (!identical(as.integer(status), 0L) || !file.exists(output)) {
  stop("candidate public-example runner failed")
}

actual <- readRDS(output)
passed <- logical(length(cases))
for (i in seq_along(cases)) {
  passed[[i]] <- is.list(actual[[i]]) && isTRUE(actual[[i]]$ok) &&
    isTRUE(all.equal(
      actual[[i]]$value,
      expected[[i]],
      tolerance = 1e-12,
      check.attributes = FALSE
    ))
  cat(sprintf("%s: %s\n", cases[[i]]$name, if (passed[[i]]) "PASS" else "FAIL"))
}
cat(sprintf("public examples: %d/%d\n", sum(passed), length(passed)))
if (!all(passed)) quit(save = "no", status = 1L)

