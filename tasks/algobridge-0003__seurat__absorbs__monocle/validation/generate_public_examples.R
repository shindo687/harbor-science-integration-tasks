suppressPackageStartupMessages(library(jsonlite))

root <- normalizePath(file.path(getwd()), mustWork = TRUE)
source(file.path(root, "tests/cases.R"), local = .GlobalEnv)
source(file.path(root, "tests/reference_runner.R"), local = .GlobalEnv)

output <- file.path(root, "public-examples")
dir.create(output, recursive = TRUE, showWarnings = FALSE)
cases <- public_cases()
for (index in seq_along(cases)) {
  case <- cases[[index]]
  stem <- sprintf("%02d-%s", index, case$name)
  write_case_json(case, file.path(output, paste0(stem, ".input.json")))
  write_json(
    run_reference(case), file.path(output, paste0(stem, ".expected.json")),
    auto_unbox = TRUE, pretty = TRUE, digits = 17, null = "null", na = "null"
  )
}
