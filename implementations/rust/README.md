# Rust DiceLab Implementation

Status: baseline implemented.

This folder contains a spec-aligned Rust implementation of DiceLab.

## Target Specs

- [../../spec/functional_spec.md](../../spec/functional_spec.md)
- [../../spec/cli_spec.md](../../spec/cli_spec.md)
- [../../spec/output_spec.md](../../spec/output_spec.md)
- [../../spec/benchmark_spec.md](../../spec/benchmark_spec.md)

## Build

From this folder:

```bash
cargo build --release
```

The binary will be produced at:

`target/release/dice-lab` (or `dice-lab.exe` on Windows)

## Run Examples

From this folder:

```bash
cargo run --release -- --rolls 10000
cargo run --release -- --rolls 10000 --seed 42 --format json
cargo run --release -- --rolls 10000 --sides 20 --format csv
cargo run --release -- --help
```

## Implemented CLI Contract

- `--rolls <int>` (required)
- `--sides <int>` (optional, default `6`)
- `--seed <int>` (optional)
- `--format <text|json|csv>` (optional, default `text`)
- `--parallel` (recognized, intentionally unsupported in baseline)
- `--help`

## Output Contract

- Deterministic ordering by face value ascending
- Required fields: total rolls, sides, distribution, mean, variance, std dev
- Supports `text`, `json`, and `csv`
- Timing/performance metrics stay in benchmark artifacts, not normal CLI output

## Learning Notes

- `src/main.rs` is heavily commented for Rust beginners.
- `clap` is used for command-line parsing.
- `rand::rngs::StdRng` is used for deterministic seeded runs.
- Statistics use streaming aggregation (sum and sum-of-squares).
