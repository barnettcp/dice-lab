# Analysis Module Restructuring Proposal

## Problem Summary

The five Python modules in `analysis/` have naming inconsistencies that make
the pipeline hard to navigate:

- Two entry points share the `run_*` prefix but have very different scope
  (`run_analysis.py` = stage 1 only; `run_analytic_pipeline.py` = both stages).
- The `build_*` prefix is used for an internal library (`build_tables.py`) and
  a CLI entry point (`build_report.py`) — structurally different roles.
- Both library modules contain the word "tables" (`build_tables.py`,
  `analyze_tables.py`), but one loads/normalises JSON and the other produces
  Plotly charts.

---

## Current Structure

```
analysis/
  run_analytic_pipeline.py   ← orchestrator: runs stage 1 + stage 2
  run_analysis.py            ← stage 1 CLI: JSON → CSVs + markdown
  build_report.py            ← stage 2 CLI: CSVs → HTML
  build_tables.py            ← library: load + normalise JSON → DataFrames
  analyze_tables.py          ← library: Plotly visualisation functions
```

### Dependency chain

```
run_analytic_pipeline.py
  ├── run_analysis.py
  │     └── build_tables.py
  └── build_report.py
        └── analyze_tables.py
```

---

## Proposed Structure

The guiding rule: **`run_*.py` = CLI entry points; everything else = library**.

| Old name                    | Proposed name    | Rationale                                                                 |
|-----------------------------|------------------|---------------------------------------------------------------------------|
| `run_analytic_pipeline.py`  | `run_pipeline.py`| Shorter; "analytic" is redundant. Still clearly an entry point.           |
| `run_analysis.py`           | `run_export.py`  | "export" accurately describes stage 1 (writes CSVs). Removes confusion with the full pipeline. |
| `build_report.py`           | `run_report.py`  | Consistent `run_` prefix for all three entry points.                      |
| `build_tables.py`           | `tables.py`      | Pure library with no CLI. "tables" matches the spec language ("canonical tables"). |
| `analyze_tables.py`         | `charts.py`      | Pure library with no CLI. Its actual output is Plotly figures, not table analysis. |

### After restructuring

```
analysis/
  run_pipeline.py    ← orchestrator: runs stage 1 + stage 2
  run_export.py      ← stage 1 CLI: JSON → CSVs + markdown
  run_report.py      ← stage 2 CLI: CSVs → HTML
  tables.py          ← library: load + normalise JSON → DataFrames
  charts.py          ← library: Plotly visualisation functions
```

Pattern is now unambiguous:
- `run_*.py` → invoke from the command line
- `tables.py` / `charts.py` → import from other modules or notebooks

---

## Import Changes Required

| File               | Old import                                     | New import                          |
|--------------------|------------------------------------------------|-------------------------------------|
| `run_pipeline.py`  | `import build_report`                          | `import run_report`                 |
| `run_pipeline.py`  | `import run_analysis`                          | `import run_export`                 |
| `run_export.py`    | `from build_tables import ...`                 | `from tables import ...`            |
| `run_report.py`    | `import analyze_tables` / `from analyze_tables import ...` | `import charts` / `from charts import ...` |

---

## Files Outside `analysis/` That Reference These Names

These must also be updated as part of the refactor:

- `Dockerfile` CMD — references `run_analytic_pipeline.py` and `run_analysis.py`
- `README.md` — references both entry point names in the Analysis Model section
- `analysis/README.md` — likely references all five module names
- `spec/analysis_spec.md` — may reference module names; review manually
- `visualization_sandbox.ipynb` — may import from `analyze_tables` or `build_tables`

---

## Execution Checklist

- [ ] Commit working baseline on `main` before branching
- [ ] Create branch `refactor/analysis-module-naming`
- [ ] Rename the five `.py` files
- [ ] Update all imports within `analysis/`
- [ ] Update `Dockerfile` CMD
- [ ] Update `README.md`
- [ ] Update `analysis/README.md`
- [ ] Review `spec/analysis_spec.md` for name references
- [ ] Review `visualization_sandbox.ipynb` for imports
- [ ] Run `python analysis/run_pipeline.py --stage analysis` (stage 1 only)
- [ ] Run `python analysis/run_pipeline.py --stage report` (stage 2 only)
- [ ] Run `python analysis/run_pipeline.py` (full pipeline)
- [ ] Run Docker pipeline end-to-end to confirm no regressions
- [ ] Delete this file or convert it to an ADR once complete
