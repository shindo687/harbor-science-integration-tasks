# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: the task's offline Harbor verifier
- Run date: 2026-08-16

| Trial | API calls | Input / cache / output tokens | Reward | Hidden result |
|---|---:|---:|---:|---:|
| `trial-1-7Ufrm97` | 213 | 26,824,418 / 26,556,544 / 151,631 | 0.466666666667 | 7/15 hidden differential cases passed; 1/5 public examples passed |
| `trial-2-U5FVcvL` | 134 | 10,207,252 / 10,026,752 / 83,394 | 0.666666666667 | 10/15 hidden differential cases passed; 3/5 public examples passed |
| `trial-3-ZWu7gZu` | 192 | 20,948,054 / 20,723,325 / 109,195 | 0.866666666667 | 13/15 hidden differential cases passed; 3/5 public examples passed |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full verifier evidence;
- `reward.txt`: verifier reward.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
