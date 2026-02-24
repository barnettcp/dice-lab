# Java DiceLab Implementation

Status: baseline implemented.

This folder contains a spec-aligned Java implementation of DiceLab.

## Target Specs

- [../../spec/functional_spec.md](../../spec/functional_spec.md)
- [../../spec/cli_spec.md](../../spec/cli_spec.md)
- [../../spec/output_spec.md](../../spec/output_spec.md)
- [../../spec/benchmark_spec.md](../../spec/benchmark_spec.md)

## Build

From this folder:

```bash
mkdir -p out
javac -d out src/DiceLab.java
```

## Run Examples

From this folder:

```bash
java -cp out DiceLab --rolls 10000
java -cp out DiceLab --rolls 10000 --seed 42 --format json
java -cp out DiceLab --rolls 10000 --sides 20 --format csv
java -cp out DiceLab --help
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

- Java compiles source (`.java`) into bytecode (`.class`) in `out/`.
- `java -cp out DiceLab ...` runs the compiled class from that classpath.
- This implementation uses no external libraries to keep beginner setup simple.
