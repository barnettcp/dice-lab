# Rust DiceLab Implementation

Status: planned (not yet implemented).

This folder will contain the Rust implementation of DiceLab aligned with the shared project specs.

## Target Specs

- [../../spec/functional_spec.md](../../spec/functional_spec.md)
- [../../spec/cli_spec.md](../../spec/cli_spec.md)
- [../../spec/output_spec.md](../../spec/output_spec.md)
- [../../spec/benchmark_spec.md](../../spec/benchmark_spec.md)

## Planned CLI Contract

The Rust implementation is expected to support:

- `--rolls <int>` (required)
- `--sides <int>` (optional, default `6`)
- `--seed <int>` (optional)
- `--format <text|json|csv>` (optional, default `text`)
- `--parallel` (optional, may be unsupported in baseline)
- `--help`

## Planned Output Contract

- Deterministic ordering by face value ascending
- Required fields: total rolls, sides, distribution, mean, variance, std dev
- `text`, `json`, `csv` output parity with other implementations
- Timing/performance metrics reported via benchmark tooling artifacts, not normal CLI output

## Build and Run (To Be Added)

Build and run commands will be documented here once implementation begins.

## Notes

- Keep this implementation self-contained and idiomatic to Rust.
- Avoid algorithm changes that would break cross-language comparability.
- Update this README as milestones are completed.
