# Python Spec → Implemented Map

This checklist maps the baseline Python implementation to project specs.

## Functional Spec Coverage

- ✅ Simulate `N` independent rolls
- ✅ Configurable sides (`--sides`, default `6`)
- ✅ Optional deterministic seed (`--seed`)
- ✅ In-memory aggregation (`face -> count`)
- ✅ Outputs total rolls, sides, distribution, mean, variance, std dev
- ✅ Population variance definition used
- ✅ Reject invalid input (`rolls <= 0`, `sides < 2`)
- ✅ Human-readable errors + non-zero exit on invalid input
- ⚠️ Parallel execution is recognized but intentionally not implemented yet

## CLI Spec Coverage

- ✅ Required `--rolls`
- ✅ Optional `--sides`, `--seed`, `--format`, `--parallel`
- ✅ Supported formats: `text`, `json`, `csv`
- ✅ `--help` provided by `argparse`
- ✅ Exit codes:
  - `0` success
  - `1` input/CLI error
  - `2` internal execution error
- ✅ Distribution ordering is ascending by face in all output modes
- ⚠️ Executable name contract (`dice-lab`) not yet packaged; currently invoked via Python script

## Output Spec Coverage

- ✅ Text output includes distribution rows as `face | count | percentage`
- ✅ JSON includes required fields and sorted distribution keys
- ✅ CSV includes `face,count,percentage` distribution rows
- ✅ Statistical summary included in each output mode

## Benchmark Spec Readiness

- ✅ No intermediate roll logging
- ✅ In-memory aggregation
- ✅ Baseline is single-threaded
- ✅ Supports benchmark workload inputs via CLI
- ⚠️ Benchmark automation script not added yet
- ⚠️ Environment/system metadata capture not added yet

## Next Minimal Milestones

1. Add script/package entry point so command can be invoked as `dice-lab`.
2. Add benchmark runner for 100 / 1,000 / 10,000 / 100,000 rolls.
3. Mirror this exact behavior in Go, Rust, and C++ before publishing comparisons.
