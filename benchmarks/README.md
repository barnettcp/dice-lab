# Benchmarks

This folder contains benchmarking tools and generated benchmark artifacts.

## Files

- `benchmark_runner.py` orchestrates benchmark runs across implementations.
- `results/` is for generated benchmark output files.

## Typical Usage

From repo root:

```bash
python benchmarks/benchmark_runner.py
python benchmarks/benchmark_runner.py --languages python cpp rust go java
```

## Pre-Benchmark Build Requirements

Build each compiled implementation first:

- C++ (from `implementations/cpp`):
	- `g++ -std=c++17 -O3 -o dice-lab src/main.cpp src/Dice.cpp`
- Rust (from `implementations/rust`):
	- `cargo build --release`
- Go (from `implementations/go`):
	- `go build -o dice-lab .`
- Java (compile into `implementations/java/out` from repo root):
	- `mkdir -p implementations/java/out`
	- `javac -d implementations/java/out implementations/java/src/DiceLab.java`

## Commit Policy

Generated benchmark outputs are ignored by default in git.

- Routine local runs should **not** be committed.
- Curated benchmark snapshots for articles/reports can be committed intentionally (for example by adjusting ignore rules or using force-add for selected files).

## Benchmarking Notes

- Keep normal CLI output and benchmark timing artifacts separate.
- Run on the same machine under similar load for fair language comparisons.
- Record exact commands and commit hashes when publishing results.
