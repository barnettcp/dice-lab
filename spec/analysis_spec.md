# analysis_spec.md

## Purpose

Define a pandas-first analysis workflow for DiceLab benchmark data that is:

- reproducible,
- article-friendly,
- and easy to evolve into an interactive app later.

This specification governs analysis behavior and outputs, not benchmark execution.

## Primary Data Source

- Input file: `benchmarks/results/benchmark_report.json`
- Source schema includes:
  - top-level benchmark metadata
  - per-batch records (`batch_records`)
  - per-language workload timing summaries (`timing_ms`)

## Analysis Goals

### 1) Cross-language comparison at fixed workload

Given one workload (for example `rolls=100000`, `sides=6`):

- compare timing distributions across languages,
- report summary metrics (mean, median, std dev, IQR),
- highlight outliers and overlap.

### 2) Within-language scaling with workload

Given one language:

- analyze timing vs rolls across all workloads,
- report scaling trend (including log-scale views),
- estimate slope-like behavior for interpretability.

### 3) Macro-batch consistency

Using `batch_records`:

- analyze elapsed time of the full benchmark cycle (`elapsed_ms`) vs `run_id`,
- assess drift/warm-up/instability,
- report trend indicators and variance over batch order.

### 4) Optional predictive modeling

Use run-level timing features to predict language label:

- clearly marked as exploratory,
- not a primary benchmark conclusion,
- include caveats about environment and confounding factors.

## Implementation Approach (Pandas First)

Analysis should be implemented as reusable Python modules using pandas DataFrames:

1. Load raw JSON
2. Normalize into tabular forms
3. Compute reusable aggregates
4. Produce report-ready tables/figures

This supports notebooks, scripts, and later Streamlit integration.

## Canonical Tables

### run_table

One row per timing sample inside a language/workload context.

Required columns:

- `batch_run_id`
- `language`
- `rolls`
- `sides`
- `trial_id` (index within `timing_ms.runs`)
- `elapsed_ms`

### batch_table

One row per full benchmark batch.

Required columns:

- `run_id`
- `started_at_utc`
- `finished_at_utc`
- `elapsed_ms`

### metadata_table (optional single-row representation)

Includes benchmark config and environment/toolchain information.

## Output Targets

Minimum outputs for pandas-first phase:

- normalized CSV exports in `shared-data/` for re-use,
- one scripted summary report (markdown or text) under `reports/`,
- plots saved under `reports/figures/`.

## Non-Goals (Current Phase)

- No mandatory web app yet.
- No Docker dependency for analysis execution.
- No hard dependency on non-pandas dataframe engines.

## Quality and Reproducibility

- Analysis scripts must run from repo root with explicit input path.
- All computed metrics should be deterministic for the same input file.
- Report output should include benchmark timestamp and source file path.

## Future Extensions

- Streamlit dashboard using the same normalized tables.
- Parquet export for larger datasets.
- Statistical significance testing modules.
