# Kimi K2.7 Code + mini-swe-agent trajectories

These are three independent Harbor attempts on this task.

- Model: `openai/kimi-k2.7-code`
- Harness: `mini-swe-agent==2.4.6`
- Maximum model output per call: `8192` tokens
- Verifier: the task's offline Harbor verifier
- Run date: 2026-08-16

| Trial | API calls | Input / cache / output tokens | Reward | Hidden result |
|---|---:|---:|---:|---:|
| `trial-1-269EU2K` | 127 | 11,330,072 / 11,163,392 / 100,466 | 0 | 0/15 |
| `trial-2-Jy3Jynb` | 117 | 5,985,229 / 5,878,272 / 43,635 | 0 | 3/15 |
| `trial-3-THUBWE3` | 160 | 14,659,733 / 14,464,448 / 89,801 | 0 | 0/15 |

Each trial directory contains:

- `raw-trajectory.json`: mini-swe-agent's native trajectory;
- `trajectory.atif.json`: Harbor's ATIF v1.7 conversion;
- `config.json`: non-secret trial configuration;
- `trial-result.json`: Harbor trial metadata and token accounting;
- `grader-results.json`: full verifier evidence;
- `reward.txt`: verifier reward.

No API credentials are stored in these files. `cost_usd=0` only means the custom
router did not provide a price mapping to Harbor; it does not imply free usage.
