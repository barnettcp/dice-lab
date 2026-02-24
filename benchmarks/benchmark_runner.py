from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


# Benchmark workloads from spec/benchmark_spec.md.
WORKLOADS = (100, 1_000, 10_000, 100_000)
DEFAULT_RUNS = 5
SUPPORTED_LANGUAGES = ("python", "cpp", "rust", "go", "java")


@dataclass(frozen=True)
class BenchmarkConfig:
    runs: int
    sides: int
    output_file: Path
    languages: tuple[str, ...]


def parse_args(argv: list[str]) -> BenchmarkConfig:
    parser = argparse.ArgumentParser(
        prog="benchmark-runner",
        description="Run DiceLab benchmark workloads and emit timing report JSON.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--sides", type=int, default=6)
    parser.add_argument(
        "--output",
        default="benchmarks/results/benchmark_report.json",
        help="Output JSON path for benchmark report.",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["python"],
        help="Languages to benchmark. Supported: python cpp rust go java",
    )
    args = parser.parse_args(argv)

    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    if args.sides < 2:
        raise ValueError("--sides must be at least 2")

    # Normalizing once here keeps downstream logic simpler.
    normalized_languages = tuple(language.lower() for language in args.languages)
    unsupported = [language for language in normalized_languages if language not in SUPPORTED_LANGUAGES]
    if unsupported:
        raise ValueError(
            f"Unsupported language(s): {', '.join(unsupported)}. "
            f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    return BenchmarkConfig(
        runs=args.runs,
        sides=args.sides,
        output_file=Path(args.output),
        languages=normalized_languages,
    )


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_python_cli_path(repo_root: Path) -> Path:
    return repo_root / "implementations" / "python" / "dice_lab.py"


def get_cpp_binary_path(repo_root: Path) -> Path:
    # On Windows + Git Bash, binaries may appear as either dice-lab.exe or dice-lab.
    # We accept both to avoid shell/toolchain-specific naming surprises.
    base = repo_root / "implementations" / "cpp"
    exe_path = base / "dice-lab.exe"
    plain_path = base / "dice-lab"
    if exe_path.exists():
        return exe_path
    if plain_path.exists():
        return plain_path
    return exe_path if os.name == "nt" else plain_path


def get_rust_binary_path(repo_root: Path) -> Path:
    # Rust release artifact can also be seen with/without .exe depending on shell context.
    # Checking both keeps benchmark discovery robust across environments.
    base = repo_root / "implementations" / "rust" / "target" / "release"
    exe_path = base / "dice-lab.exe"
    plain_path = base / "dice-lab"
    if exe_path.exists():
        return exe_path
    if plain_path.exists():
        return plain_path
    return exe_path if os.name == "nt" else plain_path


def get_go_binary_path(repo_root: Path) -> Path:
    # Go builds on Windows may still produce a no-extension file in Git Bash workflows.
    # Prefer whichever artifact actually exists.
    base = repo_root / "implementations" / "go"
    exe_path = base / "dice-lab.exe"
    plain_path = base / "dice-lab"
    if exe_path.exists():
        return exe_path
    if plain_path.exists():
        return plain_path
    return exe_path if os.name == "nt" else plain_path


def get_java_out_dir(repo_root: Path) -> Path:
    return repo_root / "implementations" / "java" / "out"


def get_java_main_class_path(repo_root: Path) -> Path:
    return get_java_out_dir(repo_root) / "DiceLab.class"


def ensure_language_ready(language: str, repo_root: Path) -> None:
    # We fail early with targeted guidance so benchmark runs do not partially succeed.
    if language == "python":
        # Python runs a script directly, so we only need the source entry file.
        python_entry = get_python_cli_path(repo_root)
        if not python_entry.exists():
            raise ValueError(f"Python entry script not found: {python_entry}")
        return

    if language == "cpp":
        # C++ benchmarks run a prebuilt native binary.
        cpp_binary = get_cpp_binary_path(repo_root)
        if not cpp_binary.exists():
            raise ValueError(
                "C++ binary not found. Build first from implementations/cpp with: "
                "g++ -std=c++17 -O3 -o dice-lab src/main.cpp src/Dice.cpp"
            )
        return

    if language == "rust":
        # Rust benchmarks run the prebuilt release binary for fair timing.
        rust_binary = get_rust_binary_path(repo_root)
        if not rust_binary.exists():
            raise ValueError(
                "Rust release binary not found. Build first from implementations/rust with: "
                "cargo build --release"
            )
        return

    if language == "go":
        # Go benchmarks run a prebuilt binary from implementations/go.
        go_binary = get_go_binary_path(repo_root)
        if not go_binary.exists():
            raise ValueError(
                "Go binary not found. Build first from implementations/go with: "
                "go build -o dice-lab ."
            )
        return

    if language == "java":
        # Java benchmark executes JVM bytecode; we verify class compilation happened.
        java_main_class = get_java_main_class_path(repo_root)
        if not java_main_class.exists():
            raise ValueError(
                "Java compiled class not found. Build first from implementations/java with: "
                "mkdir -p out && javac -d out src/DiceLab.java"
            )
        return

    raise ValueError(f"Unsupported language: {language}")


def build_command(language: str, repo_root: Path, rolls: int, sides: int) -> tuple[list[str], Path]:
    # All benchmarks use --format text and no --parallel per benchmark spec.
    if language == "python":
        # Python command: interpreter + script path + standardized benchmark args.
        command = [
            sys.executable,
            str(get_python_cli_path(repo_root)),
            "--rolls",
            str(rolls),
            "--sides",
            str(sides),
            "--format",
            "text",
        ]
        return command, repo_root

    if language == "cpp":
        # C++ command: invoke compiled binary directly.
        command = [
            str(get_cpp_binary_path(repo_root)),
            "--rolls",
            str(rolls),
            "--sides",
            str(sides),
            "--format",
            "text",
        ]
        return command, repo_root

    if language == "rust":
        # Rust command: invoke compiled release binary directly.
        command = [
            str(get_rust_binary_path(repo_root)),
            "--rolls",
            str(rolls),
            "--sides",
            str(sides),
            "--format",
            "text",
        ]
        return command, repo_root

    if language == "go":
        # Go command: invoke compiled binary directly.
        command = [
            str(get_go_binary_path(repo_root)),
            "--rolls",
            str(rolls),
            "--sides",
            str(sides),
            "--format",
            "text",
        ]
        return command, repo_root

    if language == "java":
        # Java command: run DiceLab class from compiled output directory via JVM classpath.
        command = [
            "java",
            "-cp",
            str(get_java_out_dir(repo_root)),
            "DiceLab",
            "--rolls",
            str(rolls),
            "--sides",
            str(sides),
            "--format",
            "text",
        ]
        return command, repo_root

    raise ValueError(f"Unsupported language: {language}")


def run_single_measurement_ms(command: list[str], cwd: Path) -> float:
    # We capture output to avoid console I/O noise affecting timing.
    start = time.perf_counter()
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    end = time.perf_counter()
    return (end - start) * 1000


def summarize_timings(values: list[float]) -> dict[str, float | list[float]]:
    # Mean + standard deviation support both quick comparison and stability checks.
    mean_value = statistics.fmean(values)
    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "runs": values,
        "mean": mean_value,
        "std_dev": std_dev,
        "min": min(values),
        "max": max(values),
    }


def build_language_report(config: BenchmarkConfig, repo_root: Path, language: str) -> dict:
    report_workloads: list[dict] = []
    for rolls in WORKLOADS:
        command, cwd = build_command(
            language=language,
            repo_root=repo_root,
            rolls=rolls,
            sides=config.sides,
        )
        measurements = [
            # Repeated process launches match benchmark spec expectations.
            run_single_measurement_ms(command=command, cwd=cwd)
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
        "language": language,
        "implementation": "baseline",
        "workloads": report_workloads,
    }


def build_report(config: BenchmarkConfig) -> dict:
    repo_root = get_repo_root()

    # Validate prerequisites up front so we fail before any long benchmark run starts.
    for language in config.languages:
        ensure_language_ready(language, repo_root)

    language_reports = [
        build_language_report(config=config, repo_root=repo_root, language=language)
        for language in config.languages
    ]

    return {
        "tool": "benchmarks/benchmark_runner.py",
        "benchmark_config": {
            "runs_per_workload": config.runs,
            "sides": config.sides,
            "workloads": list(WORKLOADS),
            "languages": list(config.languages),
        },
        "results": language_reports,
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "cpu": platform.processor(),
            "cores_logical": os.cpu_count(),
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
