# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: the task's offline Harbor verifier
- Run date: 2026-08-16

| Trial | API calls | Input / cache / output tokens | Reward | Hidden result |
|---|---:|---:|---:|---:|
| `trial-1-ed6bDKa` | 8 | 40,953 / 33,024 / 24,986 | 0.0000000000 | 0.0000000000 |
| `trial-2-haXH2jb` | 12 | 51,366 / 44,032 / 24,933 | 0.0000000000 | 0.0000000000 |
| `trial-3-jThz9D5` | 11 | 51,588 / 37,888 / 24,954 | 0.0000000000 | 0.0000000000 |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full verifier evidence;
- `reward.txt`: verifier reward.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
