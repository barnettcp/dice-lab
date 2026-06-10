# ADR-0001: Analysis Module Naming

## Status

Accepted

## Context

The five Python modules in `analysis/` had naming inconsistencies that made
the pipeline hard to navigate:

- Two entry points shared the `run_*` prefix but had very different scope:
  `run_analysis.py` ran stage 1 only, while `run_analytic_pipeline.py` ran
  both stages. Nothing in the names signalled this distinction.
- The `build_*` prefix was used for both an internal library (`build_tables.py`,
  no CLI) and a CLI entry point (`build_report.py`), conflating two structurally
  different roles under the same naming pattern.
- Both library modules contained the word "tables" (`build_tables.py`,
  `analyze_tables.py`), but one loaded and normalised JSON into DataFrames while
  the other produced Plotly figures — opposite ends of the pipeline with a shared
  keyword that implied similarity.

## Decision

Adopt a single naming rule across the module: **`run_*.py` files are CLI entry
points; all other `.py` files are importable libraries.**

| Old name                   | New name         | Reason                                                                 |
|----------------------------|------------------|------------------------------------------------------------------------|
| `run_analytic_pipeline.py` | `run_pipeline.py`| Shorter; "analytic" was redundant.                                     |
| `run_analysis.py`          | `run_export.py`  | "export" accurately describes the output (CSVs). Removes ambiguity with the full pipeline. |
| `build_report.py`          | `run_report.py`  | Consistent `run_` prefix for all CLI entry points.                     |
| `build_tables.py`          | `tables.py`      | Pure library. Name matches the spec language ("canonical tables").     |
| `analyze_tables.py`        | `charts.py`      | Pure library. Actual output is Plotly figures, not table analysis.     |

The `--stage analysis` option in `run_pipeline.py` was also renamed to
`--stage export` to stay consistent with the new entry point name.

## Consequences

- The `analysis/` directory now has an unambiguous contract: `run_*.py` files
  are invoked from the command line; `tables.py` and `charts.py` are imported.
- All internal imports, the `Dockerfile` CMD, both `README.md` files,
  `analysis/templates/methodology.html`, and the `--stage` CLI option were
  updated as part of this change.
- Any external scripts, notebooks, or documentation referencing the old names
  (`run_analysis`, `build_report`, `build_tables`, `analyze_tables`,
  `run_analytic_pipeline`) will need to be updated.
