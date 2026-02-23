# C++ Spec → Implemented Map

This checklist maps the current C++ baseline to project specs.

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
- ⚠️ C++ build automation for benchmark runs is not yet wired into benchmark tooling

## Next Minimal Milestones

1. Add a small C++ smoke-test strategy (or command checks) for deterministic seed behavior.
2. Optionally add build-task automation to standardize `-O3` release builds.
3. Keep output parity checks in sync against Python/Rust as Go is added.
