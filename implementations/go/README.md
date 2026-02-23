# Go DiceLab Implementation

Status: baseline implemented.

This folder contains a spec-aligned Go implementation of DiceLab.

## Target Specs

- [../../spec/functional_spec.md](../../spec/functional_spec.md)
- [../../spec/cli_spec.md](../../spec/cli_spec.md)
- [../../spec/output_spec.md](../../spec/output_spec.md)
- [../../spec/benchmark_spec.md](../../spec/benchmark_spec.md)

## Build

From this folder:

```bash
go build -o dice-lab .
```

## Run Examples

From this folder:

```bash
./dice-lab --rolls 10000
./dice-lab --rolls 10000 --seed 42 --format json
./dice-lab --rolls 10000 --sides 20 --format csv
./dice-lab --help
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

- `main.go` is commented for Go beginners.
- Standard `flag` package is used for CLI parsing.
- `rand.New(rand.NewSource(seed))` enables deterministic seeded runs.
- `strings.Builder` is used to build output efficiently.
- Statistics use streaming aggregation (sum and sum-of-squares).
