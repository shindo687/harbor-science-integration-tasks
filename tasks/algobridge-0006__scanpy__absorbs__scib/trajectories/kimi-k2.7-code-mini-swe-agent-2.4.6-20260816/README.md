# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: the task's offline Harbor verifier
- Run date: 2026-08-16

| Trial | API calls | Input / cache / output tokens | Reward | Hidden result |
|---|---:|---:|---:|---:|
| `trial-1-5rb3a7J` | 91 | 5,743,247 / 5,573,120 / 58,159 | 0 | 0 |
| `trial-2-bJBDa3a` | 86 | 4,185,553 / 4,063,424 / 33,437 | 0 | 0 |
| `trial-3-vAy6zvx` | 75 | 3,437,522 / 3,330,432 / 26,821 | 0 | 0 |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full verifier evidence;
- `reward.txt`: verifier reward.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
