from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


WORKLOADS = (100, 1_000, 10_000, 100_000)
DEFAULT_RUNS = 5


@dataclass(frozen=True)
class BenchmarkConfig:
    runs: int
    sides: int
    output_file: Path


def parse_args(argv: list[str]) -> BenchmarkConfig:
    parser = argparse.ArgumentParser(
        prog="benchmark-runner",
        description="Run DiceLab benchmark workloads and emit timing report JSON.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--sides", type=int, default=6)
    parser.add_argument(
        "--output",
        default="benchmarks/results/python_benchmark_report.json",
        help="Output JSON path for benchmark report.",
    )
    args = parser.parse_args(argv)

    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    if args.sides < 2:
        raise ValueError("--sides must be at least 2")

    return BenchmarkConfig(
        runs=args.runs,
        sides=args.sides,
        output_file=Path(args.output),
    )


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_python_cli_path(repo_root: Path) -> Path:
    return repo_root / "implementations" / "python" / "dice_lab.py"


def run_single_measurement_ms(command: list[str], cwd: Path) -> float:
    start = time.perf_counter()
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    end = time.perf_counter()
    return (end - start) * 1000


def summarize_timings(values: list[float]) -> dict[str, float | list[float]]:
    mean_value = statistics.fmean(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "runs": values,
        "mean": mean_value,
        "std_dev": std_dev,
        "min": min(values),
        "max": max(values),
    }


def build_report(config: BenchmarkConfig) -> dict:
    repo_root = get_repo_root()
    cli_path = get_python_cli_path(repo_root)

    report_workloads: list[dict] = []
    for rolls in WORKLOADS:
        command = [
            sys.executable,
            str(cli_path),
            "--rolls",
            str(rolls),
            "--sides",
            str(config.sides),
            "--format",
            "text",
        ]
        measurements = [
            run_single_measurement_ms(command=command, cwd=repo_root)
            for _ in range(config.runs)
        ]
        report_workloads.append(
            {
                "workload": {
                    "rolls": rolls,
                    "sides": config.sides,
                    "parallel": False,
                },
                "timing_ms": summarize_timings(measurements),
            }
        )

    return {
        "language": "python",
        "implementation": "baseline",
        "tool": "benchmarks/benchmark_runner.py",
        "workloads": report_workloads,
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "cpu": platform.processor(),
            "cores_logical": None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    try:
        config = parse_args(args)
        report = build_report(config)
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        config.output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Execution error: benchmarked command failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
