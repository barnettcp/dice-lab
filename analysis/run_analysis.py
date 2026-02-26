from __future__ import annotations

import argparse
from pathlib import Path

from pandas_analysis import build_frames, load_report, summarize_language_workloads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run-analysis",
        description="Build pandas-first benchmark analysis tables and summary artifacts.",
    )
    parser.add_argument(
        "--input",
        default="benchmarks/results/benchmark_report.json",
        help="Path to benchmark JSON report.",
    )
    parser.add_argument(
        "--shared-output-dir",
        default="shared-data",
        help="Directory for normalized CSV outputs.",
    )
    parser.add_argument(
        "--report-output",
        default="reports/analysis_summary.md",
        help="Path for markdown summary report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input error: benchmark report not found: {input_path}")
        return 1

    report = load_report(input_path)
    frames = build_frames(report)
    summary = summarize_language_workloads(frames.run_table)

    shared_output_dir = Path(args.shared_output_dir)
    shared_output_dir.mkdir(parents=True, exist_ok=True)

    run_table_path = shared_output_dir / "analysis_run_table.csv"
    batch_table_path = shared_output_dir / "analysis_batch_table.csv"
    summary_path = shared_output_dir / "analysis_language_workload_summary.csv"

    frames.run_table.to_csv(run_table_path, index=False)
    frames.batch_table.to_csv(batch_table_path, index=False)
    summary.to_csv(summary_path, index=False)

    report_output = Path(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# DiceLab Analysis Summary")
    lines.append("")
    lines.append(f"Source report: `{input_path.as_posix()}`")
    lines.append(f"Run table rows: {len(frames.run_table)}")
    lines.append(f"Batch rows: {len(frames.batch_table)}")
    lines.append("")

    if not frames.metadata_table.empty:
        metadata = frames.metadata_table.iloc[0]
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- Benchmark start: {metadata.get('benchmark_started_at_utc')}")
        lines.append(f"- Benchmark end: {metadata.get('benchmark_finished_at_utc')}")
        lines.append(f"- Languages: {metadata.get('languages')}")
        lines.append(f"- Runs per workload: {metadata.get('runs_per_workload')}")
        lines.append(f"- Batch runs: {metadata.get('batch_runs')}")
        lines.append("")

    lines.append("## Mean Timing by Language and Workload")
    lines.append("")

    # Keep markdown output concise but useful.
    for _, row in summary.iterrows():
        lines.append(
            "- "
            f"{row['language']} | rolls={int(row['rolls'])} | "
            f"mean={row['mean_ms']:.3f} ms | median={row['median_ms']:.3f} ms | "
            f"std={0.0 if row['std_ms'] != row['std_ms'] else row['std_ms']:.3f} ms"
        )

    report_output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {run_table_path}")
    print(f"Wrote: {batch_table_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
