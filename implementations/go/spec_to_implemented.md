# Go Spec → Implemented Map

This checklist maps the current Go baseline to project specs.

## Functional Spec Coverage

- ✅ Simulate `N` independent rolls
- ✅ Configurable sides (`--sides`, default `6`)
- ✅ Optional deterministic seed (`--seed`)
- ✅ In-memory aggregation (`face -> count`)
- ✅ Outputs total rolls, sides, distribution, mean, variance, std dev
- ✅ Population variance definition used
- ✅ Reject invalid input (`rolls <= 0`, `sides < 2`)
- ✅ Human-readable errors + non-zero exit on invalid input
- ⚠️ Parallel execution recognized but intentionally unsupported in baseline

## CLI Spec Coverage

- ✅ Required `--rolls`
- ✅ Optional `--sides`, `--seed`, `--format`, `--parallel`
- ✅ Supported formats: `text`, `json`, `csv`
- ✅ `--help` supported
- ✅ Distribution ordering is ascending by face in all output modes
- ✅ Exit codes:
  - `0` success
  - `1` input/CLI error
  - `2` internal execution error

## Output Spec Coverage

- ✅ Text output includes distribution rows as `face | count | percentage`
- ✅ JSON includes required fields and sorted distribution keys
- ✅ CSV includes `face,count,percentage` distribution rows
- ✅ Summary statistics included in all output modes

## Benchmark Spec Readiness

- ✅ No intermediate roll logging
- ✅ In-memory aggregation
- ✅ Baseline is single-threaded
- ✅ Supports benchmark workload inputs via CLI
- ⚠️ Go binary wiring in benchmark orchestrator is not yet added

## Next Minimal Milestones

1. Add Go into benchmark runner command map.
2. Add a small Go test file for deterministic seed behavior.
3. Keep output parity checks synced with Python/C++/Rust.
