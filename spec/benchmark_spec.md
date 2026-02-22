# benchmark_spec.md

## 1. Purpose

This document defines the benchmarking methodology for DiceLab.

The goal is to ensure fair, reproducible, and defensible performance comparisons across multiple language implementations.

All benchmark results referenced in documentation or articles must adhere to this specification.


## 2. Benchmark Objectives

The benchmarking process aims to measure:

1. Execution time (primary metric)
2. Compilation time (where applicable)
3. Binary size (where applicable)
4. Memory usage (optional, if measured consistently)

The primary focus is execution time for dice simulation workloads.


## 3. Test Workloads

All implementations must be tested using the following roll counts:

- 100
- 1,000
- 10,000
- 100,000

Optional extended test:

- 1,000,000 (if runtime remains reasonable)

Each workload must use:

- Default sides: 6
- No parallel flag (baseline measurement)
- No debug logging
- Output format: text (or a standardized minimal mode if defined)


## 4. Build Configuration Requirements

To ensure fairness, builds must use optimized settings.

### Python
- Standard interpreter
- No debug instrumentation
- No profiling enabled during execution

### Rust
- Build in release mode
- Debug builds must not be benchmarked

### Go
- Default `go build` (optimized by default)

### C++
- Use compiler optimization flag equivalent to `-O3`
- Debug builds must not be benchmarked

All build configurations must be documented in the article.


## 5. Measurement Methodology

### 5.1 Timing Metric

- Measure wall-clock time.
- Use high-resolution timers where available.
- Do not include compilation time in execution time measurement.

### 5.2 Repetition Policy

Each workload must be run:

- At least 5 times
- In separate executions

Report:

- Mean execution time
- Standard deviation of execution time (if possible)
- Minimum and maximum values (optional but encouraged)


## 6. Environment Control

Benchmark results must include system information:

- CPU model
- Number of cores
- RAM
- Operating system
- Compiler versions
- Language versions

Benchmarks should be run:

- On a system not under heavy load
- Without other CPU-intensive processes running
- Using the same machine for all implementations


## 7. Output Normalization

To prevent output formatting from affecting timing:

- Do not print intermediate roll results.
- Perform aggregation in memory.
- Print final results only.
- Avoid excessive console output.

If necessary, a "quiet" mode may be introduced for benchmarking.


## 8. Parallel Benchmarking (Optional Extension)

If parallel execution is implemented:

- Parallel and single-threaded modes must be benchmarked separately.
- Core count must be documented.
- Speedup must be reported relative to single-threaded baseline.
- No artificial workload inflation to exaggerate speedup.

Parallel results must not replace baseline results.


## 9. Compilation Time Measurement (Optional)

For compiled languages:

- Measure clean build time.
- Measure incremental build time (optional).
- Exclude dependency installation time.
- Record toolchain versions.

Compilation time must be clearly separated from execution benchmarks.


## 10. Binary Size Comparison (Optional)

For compiled languages:

- Report size of release binary.
- Note whether binary is statically or dynamically linked.
- Python scripts may report source size for reference.


## 11. Memory Measurement (Optional Advanced Metric)

If measured, memory usage must:

- Be recorded using consistent tooling.
- Measure peak resident memory during execution.
- Be clearly labeled as approximate.

If accurate measurement is not possible, omit this metric.


## 12. Fairness Rules

The following are prohibited:

- Artificial micro-optimizations in one language only
- Using different algorithms across implementations
- Removing statistical calculations in one version
- Using third-party high-performance libraries in only one language

All implementations must follow the functional specification exactly.


## 13. Reporting Guidelines

When publishing results:

- Show raw numbers
- Show relative comparisons
- Avoid exaggerated claims
- Explain trade-offs beyond speed
- Discuss ergonomics and developer experience

The goal is education, not declaring a winner.


## 14. Known Benchmark Limitations

This benchmark:

- Measures CPU-bound performance only
- Does not measure network I/O
- Does not measure real-world production latency
- Does not represent large-scale distributed systems

Conclusions must be limited to this workload.


## 15. Reproducibility

To maximize reproducibility:

- Tag repository versions used for benchmarks
- Record exact commit hash
- Document exact CLI commands used
- Publish benchmark script if applicable

Benchmarks should be reproducible by any user cloning the repository.
