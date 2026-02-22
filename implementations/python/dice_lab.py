from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import dataclass
from io import StringIO
from typing import Sequence


@dataclass(frozen=True)
class SimulationResult:
    total_rolls: int
    sides: int
    distribution: dict[int, int]
    mean: float
    variance: float
    std_dev: float


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dice-lab",
        description="Simulate dice rolls and report distribution + statistics.",
    )

    parser.add_argument(
        "--rolls",
        type=int,
        required=True,
        help="Total number of rolls to simulate (must be > 0).",
    )
    parser.add_argument(
        "--sides",
        type=int,
        default=6,
        help="Number of die sides (must be >= 2). Default: 6.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed for deterministic RNG behavior.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "csv"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Requested parallel execution (not implemented in Python baseline).",
    )

    args = parser.parse_args(argv)

    if args.rolls <= 0:
        raise ValueError("--rolls must be greater than 0.")
    if args.sides < 2:
        raise ValueError("--sides must be greater than or equal to 2.")

    return args


def run_simulation(rolls: int, sides: int, seed: int | None) -> SimulationResult:
    # Use a local Random instance so seeding here does not affect global random state.
    rng = random.Random(seed)

    # Pre-initialize counts for every face so output is deterministic and complete.
    counts = {face: 0 for face in range(1, sides + 1)}

    # We accumulate sum and sum-of-squares on the fly to avoid storing every roll.
    total = 0.0
    total_sq = 0.0

    for _ in range(rolls):
        value = rng.randint(1, sides)
        counts[value] += 1
        total += value
        total_sq += value * value

    mean = total / rolls

    # Population variance definition from spec: Sum((x - mean)^2) / N
    # Algebraically equivalent and efficient form using E[x^2] - (E[x])^2.
    variance = (total_sq / rolls) - (mean * mean)

    # Tiny negatives can occur from floating point rounding; clamp to zero.
    variance = max(0.0, variance)
    std_dev = math.sqrt(variance)

    return SimulationResult(
        total_rolls=rolls,
        sides=sides,
        distribution=counts,
        mean=mean,
        variance=variance,
        std_dev=std_dev,
    )


def format_text(result: SimulationResult) -> str:
    lines: list[str] = []
    lines.append("DiceLab Results")
    lines.append(f"Total rolls: {result.total_rolls}")
    lines.append(f"Sides: {result.sides}")
    lines.append("Distribution")
    lines.append("face | count | percentage")

    for face in sorted(result.distribution):
        count = result.distribution[face]
        pct = (count / result.total_rolls) * 100
        lines.append(f"{face} | {count} | {pct:.4f}")

    lines.append("")
    lines.append("Summary Statistics")
    lines.append(f"Mean: {result.mean:.6f}")
    lines.append(f"Variance: {result.variance:.6f}")
    lines.append(f"Std Dev: {result.std_dev:.6f}")
    return "\n".join(lines)


def format_json(result: SimulationResult) -> str:
    payload = {
        "total_rolls": result.total_rolls,
        "sides": result.sides,
        "distribution": {
            str(face): result.distribution[face] for face in sorted(result.distribution)
        },
        "mean": result.mean,
        "variance": result.variance,
        "std_dev": result.std_dev,
    }
    return json.dumps(payload, indent=2)


def format_csv(result: SimulationResult) -> str:
    output = StringIO()
    writer = csv.writer(output)

    # Distribution block (required face/count/percentage header).
    writer.writerow(["face", "count", "percentage"])
    for face in sorted(result.distribution):
        count = result.distribution[face]
        pct = (count / result.total_rolls) * 100
        writer.writerow([face, count, f"{pct:.4f}"])

    # Summary block so CSV still exposes the required aggregate metrics.
    writer.writerow([])
    writer.writerow(["summary_metric", "value"])
    writer.writerow(["total_rolls", result.total_rolls])
    writer.writerow(["sides", result.sides])
    writer.writerow(["mean", f"{result.mean:.6f}"])
    writer.writerow(["variance", f"{result.variance:.6f}"])
    writer.writerow(["std_dev", f"{result.std_dev:.6f}"])

    return output.getvalue().rstrip("\n")


def render_output(result: SimulationResult, output_format: str) -> str:
    if output_format == "text":
        return format_text(result)
    if output_format == "json":
        return format_json(result)
    if output_format == "csv":
        return format_csv(result)
    raise ValueError(f"Unsupported format: {output_format}")


def main(argv: Sequence[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    try:
        parsed = parse_args(args)

        if parsed.parallel:
            # Spec allows a clear error when parallel mode is unsupported.
            raise ValueError("--parallel is not supported yet in Python implementation.")

        result = run_simulation(parsed.rolls, parsed.sides, parsed.seed)
        print(render_output(result, parsed.format))
        return 0

    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # Broad catch to map unexpected issues to code 2.
        print(f"Internal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
