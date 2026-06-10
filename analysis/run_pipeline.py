"""Full DiceLab analysis pipeline orchestrator.

Runs both pipeline stages in sequence:

1. **export** — reads the benchmark JSON report, builds the three canonical
   DataFrames, writes normalised CSVs to ``shared-data/``, and renders a
   markdown summary to ``reports/analysis_summary.md``.

2. **report** — reads those CSVs and produces the HTML report at
   ``reports/benchmark_report.html``.

Usage (from repo root)::

    python analysis/run_pipeline.py

    # Run a single stage:
    python analysis/run_pipeline.py --stage export
    python analysis/run_pipeline.py --stage report

    # Override paths:
    python analysis/run_pipeline.py \\
        --input benchmarks/results/benchmark_report.json \\
        --shared-data shared-data \\
        --reports reports
"""

from __future__ import annotations

import argparse

import run_report
import run_export


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the pipeline orchestrator.

    Args:
        argv: Argument list to parse.  Defaults to ``sys.argv[1:]`` when
            ``None``.

    Returns:
        :class:`argparse.Namespace` with ``input``, ``shared_data``,
        ``reports``, and ``stage`` attributes.
    """
    parser = argparse.ArgumentParser(
        prog="run-pipeline",
        description="Run the full DiceLab analysis pipeline: JSON → CSVs → HTML report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        default="benchmarks/results/benchmark_report.json",
        metavar="FILE",
        help="Path to the benchmark JSON report.",
    )
    parser.add_argument(
        "--shared-data",
        default="shared-data",
        metavar="DIR",
        help="Directory for normalised CSV exports.",
    )
    parser.add_argument(
        "--reports",
        default="reports",
        metavar="DIR",
        help="Directory for generated report files.",
    )
    parser.add_argument(
        "--stage",
        choices=["all", "export", "report"],
        default="all",
        help="Pipeline stage to run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the requested pipeline stage(s) and return an exit code.

    Args:
        argv: Argument list forwarded to :func:`parse_args`.  Defaults to
            ``sys.argv[1:]`` when ``None``.

    Returns:
        ``0`` on success, non-zero on failure.
    """
    args = parse_args(argv)

    if args.stage in ("all", "export"):
        print("--- Stage 1/2: export ---")
        rc = run_export.main([
            "--input", args.input,
            "--shared-output-dir", args.shared_data,
            "--report-output", f"{args.reports}/analysis_summary.md",
        ])
        if rc:
            return rc

    if args.stage in ("all", "report"):
        print("--- Stage 2/2: report ---")
        run_report.main([
            "--shared-data", args.shared_data,
            "--output", f"{args.reports}/benchmark_report.html",
        ])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
