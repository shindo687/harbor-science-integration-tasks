# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: the task's offline Harbor verifier
- Run date: 2026-08-16

| Trial | API calls | Input / cache / output tokens | Reward | Hidden result |
|---|---:|---:|---:|---:|
| `trial-1-8vhu6ex` | 129 | 9,329,381 / 9,182,976 / 84,152 | 0.0000000000 | 0.0000000000 |
| `trial-2-WLDWhYA` | 40 | 1,018,403 / 965,568 / 53,630 | 0.0000000000 | 0.0000000000 |
| `trial-3-yfyPua3` | 66 | 3,396,118 / 3,302,912 / 75,620 | 0.0000000000 | 0.0000000000 |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full verifier evidence;
- `reward.txt`: verifier reward.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
