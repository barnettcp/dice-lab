"""HTML report builder for DiceLab benchmark analysis.

Reads the three canonical CSV tables from ``shared-data/`` and writes a
self-contained, single-file HTML report to ``reports/benchmark_report.html``.

The report follows a four-section narrative structure:

1. **Introduction** — context, methodology brief, and an AI-generated
   disclaimer so readers understand the provenance of the document.
2. **Batch timing** — total elapsed time per benchmark batch run, giving
   the reader an immediate sense of warm-up behaviour and run-to-run
   stability *before* any per-language breakdowns.
3. **Cross-language comparison** — a multi-line scaling chart, a
   per-workload bar chart with a dropdown selector, and a coefficient-of-
   variation consistency chart, all shown side-by-side across all five
   languages.
4. **Per-language scaling** — a dropdown selector cycles through each
   language, revealing its scaling curve and a nested workload dropdown for
   inspecting individual trial-time histograms.

All charts are Plotly figures embedded as inline ``<div>`` + ``<script>``
blocks.  Plotly is loaded once from the public CDN, so an internet connection
is required when the HTML file is first opened in a browser.

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
    plot_cross_language_scaling,
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
# CSS
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.65;
    color: #1a1a2e;
    background: #f8f9fa;
    padding: 2rem 1rem;
}

.report-wrapper {
    max-width: 1140px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 10px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.08);
    padding: 3rem 3.5rem;
}

/* ---- Typography ---- */
h1 {
    font-size: 2.2rem;
    font-weight: 700;
    color: #0d1b2a;
    margin-bottom: 0.4rem;
}
.report-subtitle {
    font-size: 1.05rem;
    color: #6c757d;
    margin-bottom: 2.5rem;
}
h2 {
    font-size: 1.55rem;
    font-weight: 700;
    color: #0d1b2a;
    margin: 2.8rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #e9ecef;
}
h3 {
    font-size: 1.2rem;
    font-weight: 600;
    color: #1a1a2e;
    margin: 1.8rem 0 0.5rem;
}
h4 {
    font-size: 1rem;
    font-weight: 600;
    color: #495057;
    margin: 1.4rem 0 0.4rem;
}
p { margin-bottom: 1rem; color: #343a40; }
ul { padding-left: 1.4rem; margin-bottom: 1rem; }
li { margin-bottom: 0.25rem; }

/* ---- Disclaimer box ---- */
.disclaimer {
    background: #fff8e7;
    border-left: 4px solid #f0a500;
    border-radius: 4px;
    padding: 1rem 1.2rem;
    margin: 1.5rem 0 2rem;
    font-size: 0.92rem;
    color: #5a4a00;
}
.disclaimer strong { color: #3d3000; }

/* ---- Sections ---- */
.section { margin-bottom: 3rem; }

/* ---- Dropdown controls ---- */
.dropdown-control {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 1.25rem 0 0.5rem;
    flex-wrap: wrap;
}
.dropdown-control label {
    font-size: 0.9rem;
    font-weight: 600;
    color: #495057;
    white-space: nowrap;
}
.dropdown-control select {
    padding: 0.35rem 0.75rem;
    border: 1px solid #ced4da;
    border-radius: 5px;
    font-size: 0.9rem;
    background: #fff;
    cursor: pointer;
    color: #212529;
    transition: border-color 0.15s;
}
.dropdown-control select:focus {
    outline: none;
    border-color: #4a90d9;
    box-shadow: 0 0 0 2px rgba(74,144,217,0.2);
}

/* ---- Chart panels (show/hide via JS) ---- */
.chart-panel { display: none; }
.chart-panel.active { display: block; }

/* ---- Stats table ---- */
.stats-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    margin: 1rem 0 1.5rem;
}
.stats-table th, .stats-table td {
    text-align: right;
    padding: 0.45rem 0.75rem;
    border-bottom: 1px solid #e9ecef;
}
.stats-table th {
    background: #f1f3f5;
    font-weight: 600;
    color: #495057;
    text-align: center;
}
.stats-table td:first-child {
    text-align: left;
    font-weight: 600;
}
.stats-table tr:hover td { background: #f8f9fa; }

/* ---- Language badge dot (legend reference) ---- */
.lang-dot {
    display: inline-block;
    width: 11px; height: 11px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
}

/* ---- Divider ---- */
.section-divider {
    border: none;
    border-top: 1px solid #e9ecef;
    margin: 2.5rem 0;
}
"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_JS = """
/**
 * switchPanel(prefix, value)
 *
 * Generic panel-switcher used by every dropdown in the report.
 * Hides all <div> elements whose id starts with `prefix + "-"` and then
 * reveals only the one whose id is `prefix + "-" + value`.
 *
 * This single function drives both the cross-language workload dropdown
 * (prefix = "xwl") and the per-language language/histogram dropdowns.
 */
function switchPanel(prefix, value) {
    // Collect all sibling panels for this group and deactivate them.
    document.querySelectorAll('[id^="' + prefix + '-"]').forEach(function(el) {
        el.classList.remove('active');
    });
    // Activate the selected panel.
    var target = document.getElementById(prefix + '-' + value);
    if (target) { target.classList.add('active'); }
}
"""

# ---------------------------------------------------------------------------
# Low-level HTML helpers
# ---------------------------------------------------------------------------


def _fig_to_div(fig, extra_class: str = "") -> str:
    """Render a Plotly figure to an HTML fragment (no full document wrapper).

    Args:
        fig: A ``plotly.graph_objects.Figure`` instance.
        extra_class: Optional additional CSS classes to append to the outer
            container produced by ``fig.to_html``.

    Returns:
        HTML string containing the chart ``<div>`` and its inline
        ``<script>`` block.  Plotly itself is *not* included (the CDN tag
        is injected once in the document ``<head>``).
    """
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": True, "responsive": True},
    )


def _stats_table_html(workload_summary) -> str:
    """Render the workload summary as a plain HTML ``<table>``.

    Displays mean, median, std-dev, min, and max timing for every
    (language, workload) combination, formatted to two decimal places.

    Args:
        workload_summary: DataFrame from :func:`load_workload_summary`,
            optionally with a ``cv_pct`` column from
            :func:`add_coefficient_of_variation`.

    Returns:
        HTML string for a ``<table class="stats-table">``.
    """
    rows = []
    rows.append(
        "<table class='stats-table'>"
        "<thead><tr>"
        "<th>Language</th><th>Rolls</th>"
        "<th>Mean (ms)</th><th>Median (ms)</th>"
        "<th>Std (ms)</th><th>Min (ms)</th><th>Max (ms)</th>"
        "</tr></thead><tbody>"
    )
    df = workload_summary.sort_values(["language", "rolls"])
    for _, row in df.iterrows():
        lang = row["language"]
        color = LANGUAGE_COLORS.get(lang, "#888")
        label = WORKLOAD_LABELS.get(int(row["rolls"]), str(int(row["rolls"])))
        rows.append(
            f"<tr>"
            f"<td><span class='lang-dot' style='background:{color}'></span>"
            f"{LANGUAGE_DISPLAY.get(lang, lang)}</td>"
            f"<td style='text-align:center'>{label}</td>"
            f"<td>{row['mean_ms']:.2f}</td>"
            f"<td>{row['median_ms']:.2f}</td>"
            f"<td>{row['std_ms']:.2f}</td>"
            f"<td>{row['min_ms']:.2f}</td>"
            f"<td>{row['max_ms']:.2f}</td>"
            f"</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _panel(content: str, panel_id: str, active: bool = False) -> str:
    """Wrap content HTML in a show/hide panel ``<div>``.

    Args:
        content: Inner HTML to embed.
        panel_id: The ``id`` attribute for the wrapper ``<div>``.
        active: If ``True``, the panel starts visible (CSS class ``active``).

    Returns:
        HTML string for the panel wrapper.
    """
    cls = "chart-panel active" if active else "chart-panel"
    return f'<div id="{panel_id}" class="{cls}">{content}</div>'


def _dropdown(
    label: str,
    select_id: str,
    prefix: str,
    options: list[tuple[str, str]],
) -> str:
    """Render a labelled ``<select>`` dropdown.

    The dropdown calls the JS ``switchPanel(prefix, this.value)`` function
    on change, which shows the corresponding panel and hides the rest.

    Args:
        label: Human-readable label shown beside the select element.
        select_id: The ``id`` attribute for the ``<select>`` element.
        prefix: Panel prefix passed to ``switchPanel``.  Must match the
            prefix used when building the corresponding ``_panel()`` ids.
        options: List of ``(value, display_text)`` tuples for the options.
            The first option is selected by default.

    Returns:
        HTML string for the ``.dropdown-control`` wrapper.
    """
    opts = []
    for i, (val, text) in enumerate(options):
        selected = " selected" if i == 0 else ""
        opts.append(f'<option value="{val}"{selected}>{text}</option>')
    opts_html = "\n".join(opts)
    return (
        f'<div class="dropdown-control">'
        f'<label for="{select_id}">{label}</label>'
        f'<select id="{select_id}" '
        f'onchange="switchPanel(\'{prefix}\', this.value)">'
        f"{opts_html}"
        f"</select></div>"
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_intro() -> str:
    """Return the HTML for Section 1: Introduction.

    Covers the experiment design, languages tested, workload sizes, and an
    AI-generated disclaimer explaining how the report was produced.

    Returns:
        HTML string for the introductory section.
    """
    return """
<section class="section" id="intro">
<h2>1 &mdash; Introduction</h2>

<p>
This report presents the results of the <strong>DiceLab benchmark</strong>,
a cross-language experiment measuring the execution time of a simulated
dice-rolling workload implemented identically in five languages:
<strong>C++</strong>, <strong>Go</strong>, <strong>Java</strong>,
<strong>Python</strong>, and <strong>Rust</strong>.
</p>

<p>The experiment is designed to answer three questions:</p>
<ul>
  <li>How do the five implementations compare at the same workload size?</li>
  <li>How does each implementation scale as the number of rolls grows from
      100 to 1&nbsp;million?</li>
  <li>How consistent is timing within each language across repeated runs?</li>
</ul>

<h3>Methodology</h3>
<p>
Each benchmark session consists of <strong>10 batch runs</strong>.  Within
each batch, every language is executed at five workload levels
(100, 1&nbsp;K, 10&nbsp;K, 100&nbsp;K, and 1&nbsp;M rolls), each repeated
for <strong>5 trials</strong>.  This yields 50 timed observations per
(language, workload) pair — 1&nbsp;250 rows in total.
</p>
<p>
All implementations roll a configurable number of six-sided dice using a
pseudo-random number generator seeded per run.  Timing captures only the
roll loop itself, excluding process start-up and I/O overhead as much as
the CLI wrapper permits.
</p>

<div class="disclaimer">
  <strong>&#9888; AI-generated report.</strong>
  This report — including its prose, chart commentary, and section
  structure — was generated with the assistance of an AI coding assistant
  (GitHub Copilot / Claude Sonnet 4.6) as part of an article on using AI
  tools for software engineering workflows.  All figures are derived from
  real benchmark measurements; the interpretive text should be treated as a
  starting point for human review rather than a final authoritative analysis.
</div>
</section>
"""


def _section_batch(batch_table) -> str:
    """Return the HTML for Section 2: Batch Timing.

    Embeds the batch timing trend chart and provides brief interpretive text
    explaining warm-up effects and what to look for.

    Args:
        batch_table: DataFrame from :func:`load_batch_table`.

    Returns:
        HTML string for the batch timing section.
    """
    fig = plot_batch_timing_trend(batch_table)
    chart_html = _fig_to_div(fig)

    # Compute a few inline stats to make the prose data-driven.
    first_ms = batch_table.sort_values("run_id")["elapsed_ms"].iloc[0]
    last_ms  = batch_table.sort_values("run_id")["elapsed_ms"].iloc[-1]
    mean_ms  = batch_table["elapsed_ms"].mean()

    return f"""
<section class="section" id="batch-timing">
<h2>2 &mdash; Batch Timing Overview</h2>

<p>
Before examining individual languages, it is useful to look at how long
each <em>complete</em> benchmark batch took end-to-end.  Each batch
exercises all five languages across all five workload levels for five
trials — so a single batch applies <strong>125 timed executions</strong>.
</p>

<p>
The chart below plots total batch elapsed time (in milliseconds) against
batch run index.  A downward trend at the start is the expected signature
of warm-up effects: the operating system's branch predictor, file-system
cache, and — in Java's case — the JVM's JIT compiler all improve over the
first few runs.  A rising trend or high late-run variance would suggest
sustained system load or thermal throttling.
</p>

{chart_html}

<p>
The first batch completed in <strong>{first_ms/1000:.2f}&nbsp;s</strong>;
the last in <strong>{last_ms/1000:.2f}&nbsp;s</strong>.  The mean across
all ten batches was <strong>{mean_ms/1000:.2f}&nbsp;s</strong>.
</p>
</section>
"""


def _section_cross_language(workload_summary) -> str:
    """Return the HTML for Section 3: Cross-Language Comparison.

    Embeds three charts:
    - A multi-line scaling chart for all languages together.
    - A per-workload bar chart hidden behind a dropdown selector.
    - A coefficient-of-variation consistency chart.

    Args:
        workload_summary: DataFrame from :func:`load_workload_summary`.

    Returns:
        HTML string for the cross-language section.
    """
    # ---- Scaling chart (always visible) ----
    scaling_fig  = plot_cross_language_scaling(workload_summary)
    scaling_html = _fig_to_div(scaling_fig)

    # ---- Per-workload bar charts (dropdown-controlled) ----
    # Build one panel per workload; the first panel starts active.
    xwl_dropdown = _dropdown(
        label="Select workload:",
        select_id="xwl-select",
        prefix="xwl",
        options=[(str(r), f"{WORKLOAD_LABELS[r]} rolls") for r in WORKLOADS],
    )
    xwl_panels = []
    for i, rolls in enumerate(WORKLOADS):
        bar_fig  = plot_cross_language_at_workload(workload_summary, rolls)
        bar_html = _fig_to_div(bar_fig)
        xwl_panels.append(_panel(bar_html, f"xwl-{rolls}", active=(i == 0)))
    xwl_panels_html = "\n".join(xwl_panels)

    # ---- CV consistency chart (always visible) ----
    cv_fig  = plot_cross_language_consistency(workload_summary)
    cv_html = _fig_to_div(cv_fig)

    # ---- Summary stats table ----
    table_html = _stats_table_html(workload_summary)

    return f"""
<section class="section" id="cross-language">
<h2>3 &mdash; Cross-Language Comparison</h2>

<p>
This section compares all five languages directly.  We start with the
broadest view — how mean execution time evolves across the full workload
range — before zooming into individual workload snapshots and finishing
with a dimensionless consistency metric.
</p>

<h3>Scaling Trend</h3>
<p>
The chart below places all five languages on the same log-scaled x-axis.
Lines running <em>parallel</em> imply each language shares the same scaling
exponent (the workload grows proportionally for all).  A line that diverges
upward signals worse asymptotic behaviour at large inputs — most visible
for Python at the 1&nbsp;M-roll level.
</p>

{scaling_html}

<h3>Per-Workload Snapshot</h3>
<p>
Use the dropdown to inspect magnitude comparisons at a single fixed
workload.  Error bars show ±1 standard deviation across the 50 trials.
This view is particularly effective for seeing how dominant Java's JVM
startup overhead is at small workloads, and whether that gap closes at
larger ones.
</p>

{xwl_dropdown}
{xwl_panels_html}

<h3>Timing Consistency (Coefficient of Variation)</h3>
<p>
Raw standard deviation cannot be fairly compared between a language timing
at ~12&nbsp;ms (Rust) and one at ~65&nbsp;ms (Python) — the absolute
spread naturally differs.  The <strong>coefficient of variation</strong>
(CV&nbsp;=&nbsp;std&nbsp;/&nbsp;mean&nbsp;×&nbsp;100&nbsp;%) normalises
spread relative to the mean, making consistency directly comparable across
all languages.
</p>
<p>
A flat, low CV indicates reliable timing.  A high or climbing CV suggests
the language is susceptible to OS scheduling jitter, JIT warm-up
variability, or memory-pressure effects at that workload level.
</p>

{cv_html}

<h3>Summary Statistics</h3>
{table_html}
</section>
"""


def _section_per_language(run_table, workload_summary) -> str:
    """Return the HTML for Section 4: Per-Language Scaling.

    Embeds a top-level language dropdown.  Each language panel contains:
    - A scaling curve (mean ± std vs rolls, log x-axis).
    - A nested workload dropdown controlling per-workload trial histograms.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.

    Returns:
        HTML string for the per-language section.
    """
    # Top-level language dropdown.
    lang_dropdown = _dropdown(
        label="Select language:",
        select_id="lang-select",
        prefix="lang",
        options=[(lang, LANGUAGE_DISPLAY[lang]) for lang in LANGUAGES],
    )

    # Build one panel per language.
    lang_panels = []
    for i, lang in enumerate(LANGUAGES):
        display = LANGUAGE_DISPLAY[lang]
        color   = LANGUAGE_COLORS[lang]

        # --- Scaling chart for this language ---
        scale_fig  = plot_scaling_within_language(run_table, lang)
        scale_html = _fig_to_div(scale_fig)

        # --- Nested histogram dropdown for this language ---
        hist_prefix   = f"{lang}-hist"
        hist_dropdown = _dropdown(
            label="Select workload:",
            select_id=f"{lang}-hist-select",
            prefix=hist_prefix,
            options=[(str(r), f"{WORKLOAD_LABELS[r]} rolls") for r in WORKLOADS],
        )
        hist_panels = []
        for j, rolls in enumerate(WORKLOADS):
            hist_fig  = plot_trial_histogram_within_language(run_table, lang, rolls)
            hist_html = _fig_to_div(hist_fig)
            hist_panels.append(
                _panel(hist_html, f"{hist_prefix}-{rolls}", active=(j == 0))
            )
        hist_panels_html = "\n".join(hist_panels)

        # Pull a few summary numbers from workload_summary for prose.
        lang_summary = workload_summary[workload_summary["language"] == lang]
        small_mean   = lang_summary[lang_summary["rolls"] == 100]["mean_ms"].values
        large_mean   = lang_summary[lang_summary["rolls"] == 1_000_000]["mean_ms"].values
        small_str    = f"{small_mean[0]:.1f}&nbsp;ms" if len(small_mean) else "—"
        large_str    = f"{large_mean[0]:.1f}&nbsp;ms" if len(large_mean) else "—"

        lang_content = f"""
<h3>
  <span class="lang-dot" style="background:{color}"></span>
  {display}
</h3>
<p>
  Mean execution time at 100 rolls: <strong>{small_str}</strong>.
  Mean at 1&nbsp;M rolls: <strong>{large_str}</strong>.
</p>

<h4>Scaling Curve</h4>
<p>
  The line below shows how mean elapsed time changes as the workload grows.
  Error bars are ±1 standard deviation across all trials at that level.
  A nearly flat line indicates sub-linear scaling — the fixed overhead
  dominates timing at most workload sizes.
</p>
{scale_html}

<h4>Trial Distribution by Workload</h4>
<p>
  Select a workload below to examine the histogram of individual trial
  times.  A tight, symmetric histogram indicates stable timing.
  A long right tail implies occasional outlier runs — likely from OS
  scheduling preemptions or, in Java's case, JIT compilation events.
</p>
{hist_dropdown}
{hist_panels_html}
"""
        lang_panels.append(_panel(lang_content, f"lang-{lang}", active=(i == 0)))

    lang_panels_html = "\n".join(lang_panels)

    return f"""
<section class="section" id="per-language">
<h2>4 &mdash; Per-Language Scaling</h2>

<p>
The cross-language view in the previous section shows the <em>relative</em>
picture across all languages at once.  This section zooms into each
language individually, revealing the shape of its scaling curve and the
distribution of individual trial times at each workload level.
</p>
<p>
Select a language from the dropdown to load its charts.
</p>

{lang_dropdown}
{lang_panels_html}
</section>
"""


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_report(
    shared_data_dir: Path = Path("shared-data"),
    output_path: Path = Path("reports/benchmark_report.html"),
) -> None:
    """Load data, assemble all HTML sections, and write the report file.

    This is the top-level entry point called by :func:`main`.  It:

    1. Loads all three canonical CSV tables from *shared_data_dir*.
    2. Builds each of the four HTML sections by calling the section
       builder functions.
    3. Wraps them in a full HTML document shell with embedded CSS and JS.
    4. Writes the finished file to *output_path*, creating the parent
       directory if needed.

    Args:
        shared_data_dir: Directory containing the canonical CSVs written by
            ``run_analysis.py``.  Defaults to ``shared-data/`` relative to
            the current working directory (i.e. the repo root).
        output_path: Destination for the finished HTML report.  Defaults to
            ``reports/benchmark_report.html``.

    Raises:
        FileNotFoundError: Propagated from the loader functions if a CSV
            is missing from *shared_data_dir*.
    """
    print(f"[build_report] Loading tables from '{shared_data_dir}' …")
    run_table        = load_run_table(shared_data_dir)
    batch_table      = load_batch_table(shared_data_dir)
    workload_summary = load_workload_summary(shared_data_dir)

    print("[build_report] Building sections …")
    s1 = _section_intro()
    s2 = _section_batch(batch_table)
    s3 = _section_cross_language(workload_summary)
    s4 = _section_per_language(run_table, workload_summary)

    # ---- Assemble the full HTML document ----
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_REPORT_TITLE}</title>
  {_PLOTLY_CDN}
  <style>{_CSS}</style>
</head>
<body>
<div class="report-wrapper">

  <h1>{_REPORT_TITLE}</h1>
  <p class="report-subtitle">
    DiceLab cross-language benchmark — C++, Go, Java, Python, Rust
  </p>

  {s1}
  <hr class="section-divider">
  {s2}
  <hr class="section-divider">
  {s3}
  <hr class="section-divider">
  {s4}

</div>
<script>{_JS}</script>
</body>
</html>"""

    # ---- Write to disk ----
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
