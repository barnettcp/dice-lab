"""Benchmark orchestrator for the DiceLab cross-language performance study.

This script drives repeated execution of every language implementation across
the workloads defined in ``spec/benchmark_spec.md`` and writes a structured
JSON report to ``benchmarks/results/benchmark_report.json`` (or a custom path).

Usage (from repo root)::

    python benchmarks/benchmark_runner.py \\
        --languages python cpp rust go java \\
        --runs 5 \\
        --batch-runs 10

All language binaries must be pre-built before running.  The script validates
binary/script availability up front so a missing artefact fails loudly before
any timing begins.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
WORKLOADS = (100, 1_000, 10_000, 100_000, 1_000_000)
DEFAULT_RUNS = 5
SUPPORTED_LANGUAGES = ("python", "cpp", "rust", "go", "java")


@dataclass(frozen=True)
class BenchmarkConfig:
    """Immutable configuration for a single benchmark session.

    Attributes:
        runs: Number of timed trials per language/workload combination.
        batch_runs: Number of full passes over all languages and workloads.
        sides: Die face count used for every workload in this session.
        output_file: Destination path for the JSON report.
        languages: Ordered tuple of language identifiers to benchmark.
    """

    runs: int
    batch_runs: int
    sides: int
    output_file: Path
    languages: tuple[str, ...]


def parse_args(argv: list[str]) -> BenchmarkConfig:
    """Parse and validate CLI arguments, returning a populated BenchmarkConfig.

    Args:
        argv: Raw command-line argument strings (typically ``sys.argv[1:]``).

    Returns:
        A validated :class:`BenchmarkConfig` ready for use by :func:`build_report`.

    Raises:
        ValueError: If ``--runs`` or ``--batch-runs`` are less than 1, ``--sides``
            is less than 2, or any requested language is not in
            ``SUPPORTED_LANGUAGES``.
    """
    parser = argparse.ArgumentParser(
        prog="benchmark-runner",
        description="Run DiceLab benchmark workloads and emit timing report JSON.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--batch-runs",
        type=int,
        default=1,
        help="Number of full benchmark batches to run (macro-level run_id count).",
    )
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
    if args.batch_runs < 1:
        raise ValueError("--batch-runs must be at least 1")
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
        batch_runs=args.batch_runs,
        sides=args.sides,
        output_file=Path(args.output),
        languages=normalized_languages,
    )


def get_repo_root() -> Path:
    """Return the absolute path to the repository root.

    Resolved relative to this file, so it works regardless of the current
    working directory when the script is invoked.
    """
    return Path(__file__).resolve().parents[1]


def get_python_cli_path(repo_root: Path) -> Path:
    """Return the path to the Python implementation entry-point script.

    Args:
        repo_root: Absolute path to the repository root.
    """
    return repo_root / "implementations" / "python" / "dice_lab.py"


def get_cpp_binary_path(repo_root: Path) -> Path:
    """Return the resolved path to the C++ release binary.

    Checks for both ``dice-lab.exe`` and ``dice-lab`` (without extension) to
    handle Windows native, Git Bash, and Unix environments transparently.

    Args:
        repo_root: Absolute path to the repository root.
    """
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
    """Return the resolved path to the Rust release binary.

    The Cargo release artefact lives under ``implementations/rust/target/release``.
    Both ``dice-lab.exe`` and ``dice-lab`` are probed in that order.

    Args:
        repo_root: Absolute path to the repository root.
    """
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
    """Return the resolved path to the Go release binary.

    The binary is expected directly inside ``implementations/go/``.  Both
    ``dice-lab.exe`` and ``dice-lab`` are probed in that order.

    Args:
        repo_root: Absolute path to the repository root.
    """
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
    """Return the directory that holds compiled Java ``.class`` files.

    Args:
        repo_root: Absolute path to the repository root.
    """
    return repo_root / "implementations" / "java" / "out"


def get_java_main_class_path(repo_root: Path) -> Path:
    """Return the expected path to the compiled ``DiceLab.class`` artefact.

    Used by :func:`ensure_language_ready` to verify the Java implementation has
    been compiled before a benchmark run starts.

    Args:
        repo_root: Absolute path to the repository root.
    """
    return get_java_out_dir(repo_root) / "DiceLab.class"


def ensure_language_ready(language: str, repo_root: Path) -> None:
    """Verify that the required build artefact or script exists for *language*.

    Raises a descriptive :class:`ValueError` with build instructions if the
    expected entry point is missing.  Called once per language before any
    timing begins so the whole batch fails early rather than mid-run.

    Args:
        language: Lowercase language identifier (e.g. ``"rust"``, ``"java"``).
        repo_root: Absolute path to the repository root.

    Raises:
        ValueError: If the required binary, script, or class file cannot be found,
            or if *language* is not a recognised identifier.
    """
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
    """Build the subprocess command and working directory for a single benchmark trial.

    All commands are constructed with ``--format text`` and no ``--parallel`` flag
    to satisfy the baseline constraints in ``spec/benchmark_spec.md``.

    Args:
        language: Lowercase language identifier.
        repo_root: Absolute path to the repository root.
        rolls: Number of dice rolls for this workload.
        sides: Number of die sides for this workload.

    Returns:
        A ``(command, cwd)`` tuple where *command* is the argument list passed to
        :func:`subprocess.run` and *cwd* is the working directory.

    Raises:
        ValueError: If *language* is not a recognised identifier.
    """
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
    """Execute *command* once and return wall-clock elapsed time in milliseconds.

    stdout and stderr are captured and discarded so console I/O does not inflate
    timing.  The process must exit with code 0 or :class:`subprocess.CalledProcessError`
    is raised.

    Args:
        command: Argument list forwarded to :func:`subprocess.run`.
        cwd: Working directory for the subprocess.

    Returns:
        Elapsed wall-clock time in milliseconds as a ``float``.
    """
    # We capture output to avoid console I/O noise affecting timing.
    start = time.perf_counter()
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    end = time.perf_counter()
    return (end - start) * 1000


def get_command_version(command: list[str], cwd: Path) -> str | None:
    """Run a version-reporting command and return its first non-empty output line.

    Captures both stdout and stderr to handle tools that write version info to
    either stream (e.g. ``java -version`` writes to stderr).  Returns ``None``
    if the command fails or produces no output.

    Args:
        command: Argument list for the version command (e.g. ``["rustc", "--version"]``).
        cwd: Working directory for the subprocess.

    Returns:
        First non-empty line of output, or ``None`` on failure.
    """
    # Returns first non-empty output line for a version command, or None if unavailable.
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "").strip()
        if not output:
            output = (completed.stderr or "").strip()
        if not output:
            return None
        return output.splitlines()[0].strip()
    except Exception:
        return None


def collect_toolchain_versions(repo_root: Path) -> dict[str, str | None]:
    """Probe each toolchain and return a mapping of name → version string.

    Queries ``python``, ``g++``, ``rustc``, ``go``, ``java``, and ``javac``.
    Any toolchain that is unavailable or returns no output is stored as ``None``
    rather than raising an exception, so a missing toolchain does not abort the
    benchmark report.

    Args:
        repo_root: Absolute path to the repository root, used as the subprocess
            working directory for version commands.

    Returns:
        Dict mapping short toolchain names to their version strings (or ``None``).
    """
    # Toolchain metadata improves reproducibility for article/report publishing.
    return {
        "python": get_command_version([sys.executable, "--version"], cwd=repo_root),
        "cpp": get_command_version(["g++", "--version"], cwd=repo_root),
        "rust": get_command_version(["rustc", "--version"], cwd=repo_root),
        "go": get_command_version(["go", "version"], cwd=repo_root),
        "java": get_command_version(["java", "-version"], cwd=repo_root),
        "javac": get_command_version(["javac", "-version"], cwd=repo_root),
    }


def summarize_timings(values: list[float]) -> dict[str, float | list[float]]:
    """Compute summary statistics for a list of timing samples.

    Matches the benchmark report schema defined in ``spec/output_spec.md``.
    Standard deviation is 0 when only one sample is present (population of one).

    Args:
        values: Raw timing measurements in milliseconds.

    Returns:
        Dict with keys ``runs``, ``mean``, ``std_dev``, ``min``, and ``max``.
    """
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


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a ``Z`` suffix.

    Example return value: ``"2026-02-26T06:24:00.393536Z"``.
    """
    # ISO-8601 UTC timestamp for traceability across benchmark sessions.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_measurements(command: list[str], cwd: Path, runs: int) -> list[float]:
    """Execute *command* exactly *runs* times and return all elapsed times.

    Each invocation is a fully independent subprocess launch, matching the
    repeated-execution requirement in ``spec/benchmark_spec.md``.

    Args:
        command: Argument list forwarded to :func:`run_single_measurement_ms`.
        cwd: Working directory for each subprocess.
        runs: Number of timed repetitions to perform.

    Returns:
        List of elapsed wall-clock times in milliseconds, one per trial.
    """
    # These are per-workload trial timings within one batch run.
    return [
        run_single_measurement_ms(command=command, cwd=cwd)
        for _ in range(runs)
    ]


def build_language_report(config: BenchmarkConfig, repo_root: Path, language: str) -> dict:
    """Run all workloads for a single language and return the report dict.

    Iterates over every roll count in ``WORKLOADS``, runs ``config.runs`` timed
    trials for each, and wraps the results in the schema expected by
    ``spec/output_spec.md``.

    Args:
        config: Active benchmark configuration.
        repo_root: Absolute path to the repository root.
        language: Lowercase language identifier to benchmark.

    Returns:
        Dict with keys ``language``, ``implementation``, and ``workloads``.
    """
    report_workloads: list[dict] = []
    for rolls in WORKLOADS:
        command, cwd = build_command(
            language=language,
            repo_root=repo_root,
            rolls=rolls,
            sides=config.sides,
        )
        # Repeated process launches match benchmark spec expectations.
        measurement_values = run_measurements(command=command, cwd=cwd, runs=config.runs)
        report_workloads.append(
            {
                "workload": {
                    "rolls": rolls,
                    "sides": config.sides,
                    "parallel": False,
                },
                "timing_ms": summarize_timings(measurement_values),
            }
        )

    return {
        "language": language,
        "implementation": "baseline",
        "workloads": report_workloads,
    }


def build_report(config: BenchmarkConfig) -> dict:
    """Execute the full benchmark session and return the complete report dict.

    Validates all language prerequisites, then runs ``config.batch_runs`` full
    passes over every language in ``config.languages``.  Each pass records
    per-language workload timings plus macro batch elapsed time.  Toolchain
    version strings and system environment metadata are appended at the end.

    Args:
        config: Validated benchmark configuration from :func:`parse_args`.

    Returns:
        Fully populated report dict matching the schema in ``spec/output_spec.md``.

    Raises:
        ValueError: If any required language artefact is missing (re-raised from
            :func:`ensure_language_ready`).
        subprocess.CalledProcessError: If a benchmarked process exits non-zero.
    """
    started_at = now_utc_iso()
    repo_root = get_repo_root()

    # Validate prerequisites up front so we fail before any long benchmark run starts.
    for language in config.languages:
        ensure_language_ready(language, repo_root)

    batch_records: list[dict] = []
    batch_elapsed_ms_values: list[float] = []

    for batch_run_id in range(config.batch_runs):
        batch_started_at = now_utc_iso()
        batch_start_perf = time.perf_counter()

        language_reports = [
            build_language_report(config=config, repo_root=repo_root, language=language)
            for language in config.languages
        ]

        batch_elapsed_ms = (time.perf_counter() - batch_start_perf) * 1000
        batch_finished_at = now_utc_iso()

        batch_elapsed_ms_values.append(batch_elapsed_ms)
        batch_records.append(
            {
                "run_id": batch_run_id,
                "started_at_utc": batch_started_at,
                "finished_at_utc": batch_finished_at,
                "elapsed_ms": batch_elapsed_ms,
                "results": language_reports,
            }
        )

    finished_at = now_utc_iso()
    toolchains = collect_toolchain_versions(repo_root)

    # Keep a top-level results view for convenience; this points to the latest batch.
    latest_results = batch_records[-1]["results"]

    return {
        "tool": "benchmarks/benchmark_runner.py",
        "benchmark_started_at_utc": started_at,
        "benchmark_finished_at_utc": finished_at,
        "benchmark_config": {
            "batch_runs": config.batch_runs,
            "runs_per_workload": config.runs,
            "sides": config.sides,
            "workloads": list(WORKLOADS),
            "languages": list(config.languages),
        },
        "batch_timing_ms": summarize_timings(batch_elapsed_ms_values),
        "batch_records": batch_records,
        "results": latest_results,
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "cpu": platform.processor(),
            "cores_logical": os.cpu_count(),
            "toolchains": toolchains,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse arguments, run benchmarks, and write the JSON report.

    The report is both written to ``config.output_file`` and printed to stdout.
    Exit codes follow ``spec/cli_spec.md``:

    - ``0`` — success
    - ``1`` — invalid input (bad arguments or missing build artefacts)
    - ``2`` — execution error (benchmarked process failed or unexpected exception)

    Args:
        argv: Argument list to parse.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        Integer exit code.
    """
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
