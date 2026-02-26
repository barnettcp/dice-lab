from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class AnalysisFrames:
    run_table: pd.DataFrame
    batch_table: pd.DataFrame
    metadata_table: pd.DataFrame


def load_report(report_path: Path) -> dict:
    with report_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_batch_records(report: dict) -> list[dict]:
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
