# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: separate, offline, with the real H200 AlphaFold multimer cases
- Run date: 2026-08-13

| Trial | API calls | Input / cache / output tokens | Hidden result | Summary |
|---|---:|---:|---:|---|
| `LrDtpZv` | 106 | 7,238,623 / 7,111,936 / 60,613 | 0/15 | A missing `dockq_score` import triggered the host-regression hard gate. |
| `G6HDHNf` | 107 | 6,017,520 / 5,910,081 / 50,643 | 11/15 | Cases 1–11 passed; real E2E cases could not find `dockq_scores.json` because it was written in `main()` rather than `predict_structure()`. |
| `PHbib6M` | 71 | 4,818,233 / 4,592,705 / 46,136 | 14/15 | All real E2E cases passed; only the `--run_dockq` flag/default contract failed. |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full hidden-verifier evidence;
- `reward.txt`: verifier reward.

Trial 2 has complete submitted trajectories, candidate artifacts, and a finalized
11/15 grader result. Its `trial-result.json` records `CancelledError` because the
original serial batch was interrupted during verifier-container cleanup after the
grader files had been written, preventing an unnecessary fourth attempt from
starting.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
