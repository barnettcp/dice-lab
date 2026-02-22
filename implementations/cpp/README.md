# C++ DiceLab Implementation

This directory contains the spec-aligned C++ implementation of DiceLab.

## Structure

- `src/Dice.h` and `src/Dice.cpp`: Dice object + RNG behavior.
- `src/main.cpp`: CLI parsing, simulation, statistics, and output formatting.

Keeping code under `src/` is a good practice (and not overkill), especially for a portfolio project where multiple build artifacts may be added later.

## Build

Use optimized flags for benchmark-ready binaries:

```bash
g++ -std=c++17 -O3 -o dice-lab src/main.cpp src/Dice.cpp
```

## CLI Usage

```bash
./dice-lab --rolls 10000
./dice-lab --rolls 10000 --seed 42 --format json
./dice-lab --rolls 10000 --sides 20 --format csv
./dice-lab --help
```

## Supported Flags

- `--rolls <int>` (required, must be `> 0`)
- `--sides <int>` (optional, default `6`, must be `>= 2`)
- `--seed <int>` (optional, deterministic within this implementation)
- `--format <text|json|csv>` (optional, default `text`)
- `--parallel` (recognized, currently returns a clear unsupported message)

## Exit Codes

- `0` success
- `1` input/CLI error
- `2` internal execution error
