"""HTML report builder for DiceLab benchmark analysis.

Reads the three canonical CSV tables from ``shared-data/`` and writes a
self-contained, single-file HTML report to ``reports/benchmark_report.html``.

The report follows a five-section narrative structure:

1. **Introduction** — personal welcome, what the reader will find, and a
   note on AI assistance with clear author commentary placeholders.
2. **Methodology** — collapsible walkthrough of how the underlying data
   was built (benchmark design, tooling, analysis pipeline).
3. **Batch timing** — total elapsed time per benchmark batch run, with
   insight cards highlighting key statistics and warm-up behaviour.
4. **Cross-language comparison** — scaling charts, per-workload bar charts,
   ridgeline distributions, and CV consistency, each prefaced with stat
   highlights and chart interaction tips.
5. **Per-language scaling** — dropdown-driven per-language deep dives with
   scaling curves and trial histograms.

HTML is rendered from Jinja2 templates stored in ``analysis/templates/``.
CSS and JS are maintained as separate files under ``reports/assets/`` for
easier editing, then inlined at build time so the output is still a single
self-contained HTML file.

Typical usage (from repo root)::

    python analysis/build_report.py

Custom paths::

    python analysis/build_report.py \\
        --shared-data shared-data \\
        --output reports/benchmark_report.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jinja2

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------
# The analysis/ directory is not an installed package, so we insert it at the
# front of sys.path so that `import analyze_tables` resolves no matter where
# the script is invoked from (repo root, CI, etc.).
sys.path.insert(0, str(Path(__file__).parent))

from analyze_tables import (  # noqa: E402 — must follow sys.path insertion
    LANGUAGE_COLORS,
    WORKLOAD_LABELS,
    add_coefficient_of_variation,
    load_batch_table,
    load_run_table,
    load_workload_summary,
    plot_batch_timing_trend,
    plot_cross_language_at_workload,
    plot_cross_language_consistency,
    plot_mean_time_by_workload,
    plot_mean_vs_cv_all,
    plot_ridgeline,
    plot_scaling_within_language,
    plot_trial_histogram_within_language,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPORT_TITLE = "DiceLab Benchmark Report"

# Plotly is injected once via CDN in the <head>; all fig.to_html() calls use
# include_plotlyjs=False so the library never appears a second time.
_PLOTLY_CDN = (
    '<script src="https://cdn.plot.ly/plotly-latest.min.js"'
    ' charset="utf-8"></script>'
)

# Display labels for languages (used in dropdown <option> text and headings).
LANGUAGE_DISPLAY: dict[str, str] = {
    "cpp":    "C++",
    "go":     "Go",
    "java":   "Java",
    "python": "Python",
    "rust":   "Rust",
}

# Ordered list of languages as they appear throughout the report.
LANGUAGES = ["cpp", "go", "java", "python", "rust"]

# Ordered list of workload sizes matching the benchmark design.
WORKLOADS = [100, 1_000, 10_000, 100_000, 1_000_000]

# ---------------------------------------------------------------------------
# Asset loading – CSS and JS live in reports/assets/ for easy editing.
# They are read at build time and inlined so the HTML stays self-contained.
# ---------------------------------------------------------------------------

# Resolve the repo root relative to *this* file (analysis/build_report.py).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ASSETS_DIR = _REPO_ROOT / "reports" / "assets"
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _load_asset(filename: str) -> str:
    """Read a text asset from ``reports/assets/``."""
    path = _ASSETS_DIR / filename
    return path.read_text(encoding="utf-8")


def _get_jinja_env() -> jinja2.Environment:
    """Create a Jinja2 environment loaded from the templates directory."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# ---------------------------------------------------------------------------
# Plotly helper
# ---------------------------------------------------------------------------


def _fig_to_html(fig) -> str:
    """Render a Plotly figure to an HTML ``<div>`` fragment."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": True, "responsive": True},
    )


# ---------------------------------------------------------------------------
# Context builders — prepare data dicts for Jinja2 templates
# ---------------------------------------------------------------------------


def _build_methodology_context(batch_table, run_table) -> dict:
    """Compute template context for Section 2: Methodology."""
    n_batches = len(batch_table)
    n_rows = len(run_table)
    n_languages = run_table["language"].nunique()
    n_workloads = run_table["rolls"].nunique()
    trials_per = n_rows // (n_batches * n_languages * n_workloads) if n_batches else 0
    return {
        "n_batches": n_batches,
        "n_rows": f"{n_rows:,}",
        "n_languages": n_languages,
        "n_workloads": n_workloads,
        "trials_per": trials_per,
    }


def _build_batch_context(batch_table, run_table) -> dict:
    """Compute template context for Section 3: Batch Timing."""
    fig = plot_batch_timing_trend(batch_table)
    chart_html = _fig_to_html(fig)

    sorted_batch = batch_table.sort_values("run_id")
    first_ms = sorted_batch["elapsed_ms"].iloc[0]
    last_ms = sorted_batch["elapsed_ms"].iloc[-1]
    mean_ms = batch_table["elapsed_ms"].mean()
    std_ms = batch_table["elapsed_ms"].std()
    cv_pct = (std_ms / mean_ms * 100) if mean_ms else 0
    n_batches = len(batch_table)

    n_languages = run_table["language"].nunique()
    n_workloads = run_table["rolls"].nunique()
    trials_per = len(run_table) // (n_batches * n_languages * n_workloads) if n_batches else 0
    execs_per_batch = n_languages * n_workloads * trials_per

    return {
        "chart": chart_html,
        "n_batches": n_batches,
        "n_languages": n_languages,
        "n_workloads": n_workloads,
        "trials_per": trials_per,
        "execs_per_batch": execs_per_batch,
        "first_s": f"{first_ms / 1000:.2f}",
        "last_s": f"{last_ms / 1000:.2f}",
        "mean_s": f"{mean_ms / 1000:.2f}",
        "std_s": f"{std_ms / 1000:.2f}",
        "cv_pct": f"{cv_pct:.1f}",
        "stability": "very stable" if cv_pct < 3 else "moderate",
        "cards": [
            (str(n_batches), "Batch runs"),
            (f"{mean_ms / 1000:.1f} s", "Mean batch time"),
            (f"{std_ms / 1000:.2f} s", "Std deviation"),
            (f"{cv_pct:.1f}%", "Coefficient of variation"),
        ],
    }


def _build_cross_language_context(workload_summary, run_table) -> dict:
    """Compute template context for Section 4: Cross-Language Comparison."""
    ws = workload_summary.copy()
    ws = add_coefficient_of_variation(ws)

    # Stats at 1M rolls
    ws_1m = ws[ws["rolls"] == 1_000_000]
    if len(ws_1m):
        fastest_1m = ws_1m.loc[ws_1m["mean_ms"].idxmin(), "language"]
        slowest_1m = ws_1m.loc[ws_1m["mean_ms"].idxmax(), "language"]
        ratio_1m = ws_1m["mean_ms"].max() / ws_1m["mean_ms"].min()
    else:
        fastest_1m, slowest_1m, ratio_1m = "\u2014", "\u2014", 0

    mean_cv = ws.groupby("language")["cv_pct"].mean()
    most_consistent = mean_cv.idxmin()
    most_consistent_cv = mean_cv.min()

    cards = [
        (f"{ratio_1m:.1f}\u00d7",
         f"Speed gap at 1M rolls ({LANGUAGE_DISPLAY.get(slowest_1m, slowest_1m)} "
         f"vs {LANGUAGE_DISPLAY.get(fastest_1m, fastest_1m)})"),
        (LANGUAGE_DISPLAY.get(most_consistent, most_consistent),
         f"Most consistent (avg CV {most_consistent_cv:.1f}%)"),
        (f"{len(run_table):,}", "Total timed trials"),
    ]

    # Charts
    scaling_chart = _fig_to_html(plot_mean_time_by_workload(workload_summary))

    workload_options = [(str(r), f"{WORKLOAD_LABELS[r]} rolls") for r in WORKLOADS]

    xwl_charts = {}
    for rolls in WORKLOADS:
        xwl_charts[str(rolls)] = _fig_to_html(
            plot_cross_language_at_workload(workload_summary, rolls)
        )

    cv_scatter_chart = _fig_to_html(plot_mean_vs_cv_all(workload_summary))

    ridge_charts = {}
    for rolls in WORKLOADS:
        ridge_charts[str(rolls)] = _fig_to_html(
            plot_ridgeline(run_table, num_rolls=rolls)
        )

    cv_chart = _fig_to_html(plot_cross_language_consistency(workload_summary))

    # Stats table data (pre-formatted for the template)
    df = workload_summary.sort_values(["language", "rolls"])
    stats_rows = []
    for _, row in df.iterrows():
        lang = row["language"]
        stats_rows.append({
            "color": LANGUAGE_COLORS.get(lang, "#888"),
            "display": LANGUAGE_DISPLAY.get(lang, lang),
            "label": WORKLOAD_LABELS.get(int(row["rolls"]), str(int(row["rolls"]))),
            "mean_ms": f"{row['mean_ms']:.2f}",
            "median_ms": f"{row['median_ms']:.2f}",
            "std_ms": f"{row['std_ms']:.2f}",
            "min_ms": f"{row['min_ms']:.2f}",
            "max_ms": f"{row['max_ms']:.2f}",
        })

    return {
        "cards": cards,
        "scaling_chart": scaling_chart,
        "workload_options": workload_options,
        "workloads": [str(r) for r in WORKLOADS],
        "xwl_charts": xwl_charts,
        "cv_scatter_chart": cv_scatter_chart,
        "ridge_charts": ridge_charts,
        "cv_chart": cv_chart,
        "stats_rows": stats_rows,
    }


def _build_per_language_context(run_table, workload_summary) -> dict:
    """Compute template context for Section 5: Per-Language Scaling."""
    ws = add_coefficient_of_variation(workload_summary)

    workload_options = [(str(r), f"{WORKLOAD_LABELS[r]} rolls") for r in WORKLOADS]

    languages = []
    for lang in LANGUAGES:
        display = LANGUAGE_DISPLAY[lang]
        color = LANGUAGE_COLORS[lang]

        lang_ws = ws[ws["language"] == lang].sort_values("rolls")
        small_mean = lang_ws[lang_ws["rolls"] == 100]["mean_ms"].values
        large_mean = lang_ws[lang_ws["rolls"] == 1_000_000]["mean_ms"].values
        small_str = f"{small_mean[0]:.1f}" if len(small_mean) else "\u2014"
        large_str = f"{large_mean[0]:.1f}" if len(large_mean) else "\u2014"

        growth = (
            float(large_mean[0]) / float(small_mean[0])
            if (len(small_mean) and len(large_mean) and small_mean[0] > 0)
            else 0
        )
        avg_cv = lang_ws["cv_pct"].mean() if "cv_pct" in lang_ws.columns else 0

        scale_chart = _fig_to_html(plot_scaling_within_language(run_table, lang))

        hist_charts = {}
        for rolls in WORKLOADS:
            hist_charts[str(rolls)] = _fig_to_html(
                plot_trial_histogram_within_language(run_table, lang, rolls)
            )

        languages.append({
            "key": lang,
            "display": display,
            "color": color,
            "cards": [
                (f"{small_str} ms", "Mean at 100 rolls"),
                (f"{large_str} ms", "Mean at 1M rolls"),
                (f"{growth:.1f}\u00d7", "Growth factor (100 \u2192 1M)"),
                (f"{avg_cv:.1f}%", "Avg CV across workloads"),
            ],
            "scale_chart": scale_chart,
            "hist_charts": hist_charts,
        })

    return {
        "languages": languages,
        "language_options": [(lang, LANGUAGE_DISPLAY[lang]) for lang in LANGUAGES],
        "workload_options": workload_options,
        "workloads": [str(r) for r in WORKLOADS],
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_report(
    shared_data_dir: Path = Path("shared-data"),
    output_path: Path = Path("reports/benchmark_report.html"),
) -> None:
    """Load data, render the Jinja2 template, and write the report file.

    Args:
        shared_data_dir: Directory containing the canonical CSVs written by
            ``run_analysis.py``.
        output_path: Destination for the finished HTML report.
    """
    print(f"[build_report] Loading tables from '{shared_data_dir}' \u2026")
    run_table = load_run_table(shared_data_dir)
    batch_table = load_batch_table(shared_data_dir)
    workload_summary = load_workload_summary(shared_data_dir)

    print("[build_report] Loading assets \u2026")
    css = _load_asset("report.css")
    js = _load_asset("report.js")

    print("[build_report] Building report context \u2026")
    env = _get_jinja_env()
    template = env.get_template("base.html")

    context = {
        "title": _REPORT_TITLE,
        "plotly_cdn": _PLOTLY_CDN,
        "css": css,
        "js": js,
        "meth": _build_methodology_context(batch_table, run_table),
        "batch": _build_batch_context(batch_table, run_table),
        "cross": _build_cross_language_context(workload_summary, run_table),
        "per_lang": _build_per_language_context(run_table, workload_summary),
    }

    print("[build_report] Rendering template \u2026")
    html = template.render(context)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[build_report] Report written to '{output_path}'")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the report builder.

    Args:
        argv: Argument list to parse.  Defaults to ``sys.argv[1:]`` when
            ``None``.

    Returns:
        Parsed :class:`argparse.Namespace` with ``shared_data`` and
        ``output`` attributes.
    """
    parser = argparse.ArgumentParser(
        description="Build the DiceLab HTML benchmark report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--shared-data",
        default="shared-data",
        metavar="DIR",
        help="Directory containing the canonical CSV exports.",
    )
    parser.add_argument(
        "--output",
        default="reports/benchmark_report.html",
        metavar="FILE",
        help="Destination path for the generated HTML report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: parse arguments and run :func:`build_report`.

    Args:
        argv: Argument list forwarded to :func:`parse_args`.  Defaults to
            ``sys.argv[1:]`` when ``None``.
    """
    args = parse_args(argv)
    build_report(
        shared_data_dir=Path(args.shared_data),
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
