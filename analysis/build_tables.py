"""Core data transformation library for DiceLab benchmark data.

This module provides functions to load, normalise, and summarise the JSON
report produced by ``benchmarks/benchmark_runner.py``.  All public functions
operate on plain Python dicts or :class:`pandas.DataFrame` objects so they
can be consumed from scripts, notebooks, and a future Streamlit dashboard
without modification.

Canonical tables produced here are defined in ``spec/analysis_spec.md``:

- **run_table** — one row per individual timing trial.
- **batch_table** — one row per macro benchmark batch.
- **metadata_table** — single-row configuration / environment snapshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class AnalysisFrames:
    """Container for the three canonical DataFrames produced by :func:`build_frames`.

    Attributes:
        run_table: One row per timing trial.
            Columns: ``batch_run_id``, ``language``, ``rolls``, ``sides``,
            ``trial_id``, ``elapsed_ms``.
        batch_table: One row per full benchmark batch.
            Columns: ``run_id``, ``started_at_utc``, ``finished_at_utc``,
            ``elapsed_ms``.
        metadata_table: Single-row snapshot of benchmark configuration and
            system environment (OS, CPU, language versions, etc.).
    """

    run_table: pd.DataFrame
    batch_table: pd.DataFrame
    metadata_table: pd.DataFrame


def load_report(report_path: Path) -> dict:
    """Load the benchmark JSON report from disk and return it as a plain dict.

    Args:
        report_path: Path to the ``benchmark_report.json`` file.

    Returns:
        Parsed JSON content as a nested Python dict.

    Raises:
        FileNotFoundError: If *report_path* does not exist.
        json.JSONDecodeError: If the file content is not valid JSON.
    """
    with report_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_batch_records(report: dict) -> list[dict]:
    """Extract the list of batch records from the report, with a fallback.

    Modern reports contain a ``batch_records`` list.  Older reports that only
    have a top-level ``results`` list are synthesised into a single ``run_id=0``
    batch so downstream code can always assume the same structure.

    Args:
        report: Parsed benchmark report dict.

    Returns:
        List of batch-record dicts, each containing ``run_id``, timestamps,
        ``elapsed_ms``, and a ``results`` list of per-language reports.
    """
    # New schema has macro batch records. Fallback keeps compatibility if only `results` exists.
    batch_records = report.get("batch_records")
    if isinstance(batch_records, list) and batch_records:
        return batch_records

    results = report.get("results", [])
    synthetic = {
        "run_id": 0,
        "started_at_utc": report.get("benchmark_started_at_utc"),
        "finished_at_utc": report.get("benchmark_finished_at_utc"),
        "elapsed_ms": None,
        "results": results,
    }
    return [synthetic]


def build_frames(report: dict) -> AnalysisFrames:
    """Normalise a benchmark report dict into the three canonical DataFrames.

    Iterates over every batch, language, workload, and individual trial to
    flatten the nested JSON into tidy tabular form.  The resulting frames
    conform to the schema specified in ``spec/analysis_spec.md``.

    Args:
        report: Parsed benchmark report dict, typically from :func:`load_report`.

    Returns:
        :class:`AnalysisFrames` holding ``run_table``, ``batch_table``, and
        ``metadata_table``.
    """
    run_rows: list[dict] = []
    batch_rows: list[dict] = []

    for batch in _extract_batch_records(report):
        batch_run_id = int(batch.get("run_id", 0))
        batch_rows.append(
            {
                "run_id": batch_run_id,
                "started_at_utc": batch.get("started_at_utc"),
                "finished_at_utc": batch.get("finished_at_utc"),
                "elapsed_ms": batch.get("elapsed_ms"),
            }
        )

        for language_block in batch.get("results", []):
            language = language_block.get("language")
            for workload_block in language_block.get("workloads", []):
                workload = workload_block.get("workload", {})
                rolls = workload.get("rolls")
                sides = workload.get("sides")
                timing = workload_block.get("timing_ms", {})
                runs = timing.get("runs", [])

                for trial_id, elapsed_ms in enumerate(runs):
                    run_rows.append(
                        {
                            "batch_run_id": batch_run_id,
                            "language": language,
                            "rolls": rolls,
                            "sides": sides,
                            "trial_id": trial_id,
                            "elapsed_ms": float(elapsed_ms),
                        }
                    )

    run_table = pd.DataFrame(run_rows)
    batch_table = pd.DataFrame(batch_rows)

    metadata_table = pd.DataFrame(
        [
            {
                "tool": report.get("tool"),
                "benchmark_started_at_utc": report.get("benchmark_started_at_utc"),
                "benchmark_finished_at_utc": report.get("benchmark_finished_at_utc"),
                "runs_per_workload": report.get("benchmark_config", {}).get("runs_per_workload"),
                "batch_runs": report.get("benchmark_config", {}).get("batch_runs"),
                "sides": report.get("benchmark_config", {}).get("sides"),
                "languages": ",".join(report.get("benchmark_config", {}).get("languages", [])),
                "os": report.get("environment", {}).get("os"),
                "cpu": report.get("environment", {}).get("cpu"),
                "cores_logical": report.get("environment", {}).get("cores_logical"),
                "python_version": report.get("environment", {}).get("python_version"),
            }
        ]
    )

    return AnalysisFrames(
        run_table=run_table,
        batch_table=batch_table,
        metadata_table=metadata_table,
    )


def summarize_language_workloads(run_table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-trial timing rows into per-language/workload summary statistics.

    Groups ``run_table`` by ``(language, rolls, sides)`` and computes count,
    mean, median, standard deviation, min, and max of ``elapsed_ms``.
    Rows are sorted by ``rolls`` ascending then ``language`` alphabetically,
    which matches the ordering used in ``reports/analysis_summary.md``.

    Args:
        run_table: DataFrame with at minimum the columns ``language``, ``rolls``,
            ``sides``, and ``elapsed_ms`` (as produced by :func:`build_frames`).

    Returns:
        Summary DataFrame with columns: ``language``, ``rolls``, ``sides``,
        ``runs``, ``mean_ms``, ``median_ms``, ``std_ms``, ``min_ms``, ``max_ms``.
    """
    grouped = (
        run_table
        .groupby(["language", "rolls", "sides"], dropna=False)["elapsed_ms"]
        .agg(
            runs="count",
            mean_ms="mean",
            median_ms="median",
            std_ms="std",
            min_ms="min",
            max_ms="max",
        )
        .reset_index()
        .sort_values(["rolls", "language"])
    )
    return grouped
