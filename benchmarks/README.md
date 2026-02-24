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
python benchmarks/benchmark_runner.py --languages python cpp rust go java --runs 5 --batch-runs 100
```

Parameter intent:

- `--runs`: per-workload trials inside each batch
- `--batch-runs`: number of full benchmark cycles (macro-level `run_id` count)

Output shape highlights:

- `batch_records[*].run_id` identifies each full benchmark cycle
- `batch_records[*].elapsed_ms` captures total time for one full cycle
- `batch_timing_ms` summarizes full-cycle consistency across all batch runs
- `results` contains the latest batch view for convenience

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
