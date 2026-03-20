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


def _load_asset(filename: str) -> str:
    """Read a text asset from ``reports/assets/``."""
    path = _ASSETS_DIR / filename
    return path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# HTML helpers – insight cards, author notes, chart tips
# ---------------------------------------------------------------------------


def _insight_card(value: str, label: str) -> str:
    """Render a single stat-highlight card."""
    return (
        f'<div class="insight-card">'
        f'<div class="insight-value">{value}</div>'
        f'<div class="insight-label">{label}</div>'
        f'</div>'
    )


def _insight_row(cards: list[str]) -> str:
    """Wrap multiple insight cards in a flex row."""
    return '<div class="insight-row">' + "".join(cards) + "</div>"


def _chart_tip(text: str) -> str:
    """Render a small green interaction-tip box."""
    return (
        '<div class="chart-tip">'
        '<span class="tip-icon">&#128270;</span>'  # magnifying glass
        f"<span>{text}</span>"
        "</div>"
    )


def _author_note(placeholder_text: str) -> str:
    """Render a blue author-commentary placeholder box.

    The placeholder text is wrapped in ``<em class="placeholder">`` so it
    is visually distinguishable from actual author prose once filled in.
    """
    return (
        '<div class="author-note">'
        '<strong>Author\'s take:</strong> '
        f'<em class="placeholder">{placeholder_text}</em>'
        "</div>"
    )


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

    A personable welcome, what the reader will find, and a nuanced AI
    disclaimer that clarifies the author's role alongside AI tooling.

    Returns:
        HTML string for the introductory section.
    """
    return """
<section class="section" id="intro">
<h2>1 &mdash; Welcome</h2>

<p>
Thanks for reading the <strong>DiceLab benchmark report</strong>.
This is a cross-language experiment where I implemented the same
dice-rolling simulation in five languages &mdash;
<strong>C++</strong>, <strong>Go</strong>, <strong>Java</strong>,
<strong>Python</strong>, and <strong>Rust</strong> &mdash; and then
measured how they compare under identical workloads.
</p>

<p>The report is organised around three questions:</p>
<ul>
  <li>How do the five implementations compare at the same workload size?</li>
  <li>How does each implementation scale as rolls grow from
      100 to 1&nbsp;million?</li>
  <li>How consistent (repeatable) is each language's timing
      across many trials?</li>
</ul>

<p>
Everything here is interactive.  Charts are powered by
<a href="https://plotly.com/javascript/" target="_blank" rel="noopener">Plotly.js</a>,
so you can hover for details, zoom into regions, and toggle traces on
and off via the legend.  Several sections include dropdowns to switch
between workloads or languages.  I&rsquo;ve also included my own
commentary throughout &mdash; look for the blue &ldquo;Author&rsquo;s
take&rdquo; boxes.
</p>

""" + _author_note(
        "Replace this placeholder with your personal introduction &mdash; "
        "why you built DiceLab, what you hoped to learn, and anything the "
        "reader should keep in mind while exploring the data."
    ) + """

<div class="disclaimer">
  <strong>&#9888; A note on AI assistance.</strong>
  The code that generated this report &mdash; data loading, chart
  construction, and the HTML scaffolding &mdash; was written with the help
  of an AI coding assistant (GitHub Copilot).  The benchmark data itself is
  real, measured on my machine, and the interpretive prose is my own
  (except where marked as a placeholder).  Think of the AI as a power tool:
  I directed the design and reviewed every output.
</div>
</section>
"""


def _section_methodology(batch_table, run_table) -> str:
    """Return the HTML for Section 2: Methodology (collapsible).

    Walks the reader through the data pipeline: benchmark design, tooling,
    how the CSV tables were produced, and what the numbers represent.

    Args:
        batch_table: DataFrame from :func:`load_batch_table`.
        run_table: Per-trial DataFrame from :func:`load_run_table`.

    Returns:
        HTML string for the methodology section.
    """
    n_batches = len(batch_table)
    n_rows = len(run_table)
    n_languages = run_table["language"].nunique()
    n_workloads = run_table["rolls"].nunique()
    trials_per = n_rows // (n_batches * n_languages * n_workloads) if n_batches else 0

    return f"""
<section class="section" id="methodology">
<h2>2 &mdash; Methodology</h2>

<p>
Understanding <em>how</em> the data was collected is just as important as
the results themselves.  This section walks through the benchmark design,
the tooling, and the analysis pipeline so you can judge the results on
their merits.
</p>

<details class="collapsible" open>
<summary>Benchmark design &amp; data pipeline</summary>
<div class="details-body">

<ol class="methodology-steps">
  <li>
    <strong>Implementation.</strong>  The same dice simulation was coded in
    five languages (C++, Go, Java, Python, Rust), each following a shared
    <a href="https://github.com" target="_blank" rel="noopener">functional
    spec</a>.  Every implementation accepts the same CLI contract: number
    of rolls, number of sides, and an optional seed.
  </li>
  <li>
    <strong>Build configuration.</strong>  Compiled languages use optimised
    release builds (e.g.&nbsp;<code>-O3</code> for C++,
    <code>cargo build --release</code> for Rust).  Python runs on the
    standard CPython interpreter with no special flags.
  </li>
  <li>
    <strong>Benchmark execution.</strong>  The orchestrator
    (<code>benchmarks/benchmark_runner.py</code>) runs
    <strong>{n_batches} batch runs</strong>.  In each batch, every language
    is exercised at {n_workloads} workload levels
    (100, 1&nbsp;K, 10&nbsp;K, 100&nbsp;K, 1&nbsp;M rolls)
    for <strong>{trials_per} trials</strong> each.  Timing captures only the
    roll loop, excluding process start-up and I/O overhead where possible.
  </li>
  <li>
    <strong>Raw output.</strong>  The runner writes a structured JSON report
    to <code>benchmarks/results/benchmark_report.json</code> containing
    per-trial timings, batch metadata, and environment info.
  </li>
  <li>
    <strong>Analysis pipeline.</strong>  Running
    <code>python analysis/run_analysis.py</code> normalises the JSON into
    three canonical CSV tables under <code>shared-data/</code>:
    <ul>
      <li><strong>Run table</strong> &mdash; {n_rows:,} rows, one per timed
          trial (the most granular view).</li>
      <li><strong>Batch table</strong> &mdash; {n_batches} rows, one per
          full benchmark batch.</li>
      <li><strong>Workload summary</strong> &mdash; pre-aggregated mean,
          median, std, min, max per (language, workload) pair.</li>
    </ul>
  </li>
  <li>
    <strong>Report generation.</strong>  This HTML report is built from those
    CSVs by <code>python analysis/build_report.py</code>.  Charts are
    Plotly figures; prose and stats are computed at build time.
  </li>
</ol>

</div>
</details>
</section>
"""


def _section_batch(batch_table, run_table) -> str:
    """Return the HTML for Section 3: Batch Timing.

    Embeds the enhanced batch timing trend chart (with rolling-mean overlay
    and +/-1 std band), insight cards, a chart interaction tip, and an
    author commentary placeholder.

    Args:
        batch_table: DataFrame from :func:`load_batch_table`.
        run_table: Per-trial DataFrame from :func:`load_run_table`.

    Returns:
        HTML string for the batch timing section.
    """
    fig = plot_batch_timing_trend(batch_table)
    chart_html = _fig_to_div(fig)

    # Compute inline stats to make the prose data-driven.
    sorted_batch = batch_table.sort_values("run_id")
    first_ms = sorted_batch["elapsed_ms"].iloc[0]
    last_ms  = sorted_batch["elapsed_ms"].iloc[-1]
    mean_ms  = batch_table["elapsed_ms"].mean()
    std_ms   = batch_table["elapsed_ms"].std()
    cv_pct   = (std_ms / mean_ms * 100) if mean_ms else 0
    n_batches = len(batch_table)

    # Derive per-batch execution count from the data itself.
    n_languages = run_table["language"].nunique()
    n_workloads = run_table["rolls"].nunique()
    trials_per  = len(run_table) // (n_batches * n_languages * n_workloads) if n_batches else 0
    execs_per_batch = n_languages * n_workloads * trials_per

    cards = _insight_row([
        _insight_card(f"{n_batches}", "Batch runs"),
        _insight_card(f"{mean_ms/1000:.1f} s", "Mean batch time"),
        _insight_card(f"{std_ms/1000:.2f} s", "Std deviation"),
        _insight_card(f"{cv_pct:.1f}%", "Coefficient of variation"),
    ])

    tip = _chart_tip(
        "Hover over any point to see exact timing.  "
        "Click a legend entry to toggle that trace on or off.  "
        "Double-click a legend entry to isolate it."
    )

    author = _author_note(
        "What do you notice about the batch-to-batch stability?  "
        "Were there any surprising warm-up effects or late-run drift?  "
        "Replace this with your observations."
    )

    return f"""
<section class="section" id="batch-timing">
<h2>3 &mdash; Batch Timing Overview</h2>

<p>
Before examining individual languages, let&rsquo;s look at how long
each <em>complete</em> benchmark batch took end-to-end.  Each batch
exercises all {n_languages} languages across all {n_workloads} workload levels
for {trials_per} trials each &mdash;
so a single batch applies <strong>{execs_per_batch} timed executions</strong>.
</p>

{cards}

<p>
The chart below plots total batch elapsed time against batch run index.
A downward trend at the start is the expected signature of warm-up
effects: the OS&rsquo;s branch predictor, file-system cache, and &mdash;
in Java&rsquo;s case &mdash; the JVM&rsquo;s JIT compiler all improve
over the first few runs.  A rising trend or high late-run variance
would suggest sustained system load or thermal throttling.
</p>

{tip}
{chart_html}

<p>
The first batch completed in <strong>{first_ms/1000:.2f}&nbsp;s</strong>;
the last in <strong>{last_ms/1000:.2f}&nbsp;s</strong>.  Across all
{n_batches} batches the mean was <strong>{mean_ms/1000:.2f}&nbsp;s</strong>
with a standard deviation of {std_ms/1000:.2f}&nbsp;s
(CV&nbsp;=&nbsp;{cv_pct:.1f}%), indicating
{"very stable" if cv_pct < 3 else "moderate"} run-to-run performance.
</p>

{author}
</section>
"""


def _section_cross_language(workload_summary, run_table) -> str:
    """Return the HTML for Section 4: Cross-Language Comparison.

    Embeds charts with insight cards and chart interaction tips.

    Args:
        workload_summary: DataFrame from :func:`load_workload_summary`.
        run_table: Per-trial DataFrame from :func:`load_run_table`.

    Returns:
        HTML string for the cross-language section.
    """
    # ---- Compute headline stats for insight cards ----
    ws = workload_summary.copy()
    ws = add_coefficient_of_variation(ws)

    fastest_lang = ws.loc[ws["mean_ms"].idxmin(), "language"]
    fastest_mean = ws["mean_ms"].min()
    slowest_lang = ws.loc[ws["mean_ms"].idxmax(), "language"]
    slowest_mean = ws["mean_ms"].max()
    speed_ratio  = slowest_mean / fastest_mean if fastest_mean else 0

    # At 1M rolls specifically
    ws_1m = ws[ws["rolls"] == 1_000_000]
    if len(ws_1m):
        fastest_1m = ws_1m.loc[ws_1m["mean_ms"].idxmin(), "language"]
        slowest_1m = ws_1m.loc[ws_1m["mean_ms"].idxmax(), "language"]
        ratio_1m = ws_1m["mean_ms"].max() / ws_1m["mean_ms"].min()
    else:
        fastest_1m, slowest_1m, ratio_1m = "—", "—", 0

    # Most consistent (lowest CV across all workloads)
    mean_cv = ws.groupby("language")["cv_pct"].mean()
    most_consistent = mean_cv.idxmin()
    most_consistent_cv = mean_cv.min()

    cards = _insight_row([
        _insight_card(
            f"{ratio_1m:.1f}&times;",
            f"Speed gap at 1M rolls ({LANGUAGE_DISPLAY.get(slowest_1m, slowest_1m)} "
            f"vs {LANGUAGE_DISPLAY.get(fastest_1m, fastest_1m)})",
        ),
        _insight_card(
            LANGUAGE_DISPLAY.get(most_consistent, most_consistent),
            f"Most consistent (avg CV {most_consistent_cv:.1f}%)",
        ),
        _insight_card(
            f"{len(run_table):,}",
            "Total timed trials",
        ),
    ])

    # ---- Scaling chart with ±1 std band (always visible) ----
    scaling_fig  = plot_mean_time_by_workload(workload_summary)
    scaling_html = _fig_to_div(scaling_fig)

    # ---- Per-workload bar charts (dropdown-controlled) ----
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

    # ---- Mean vs CV scatter (always visible) ----
    cv_scatter_fig  = plot_mean_vs_cv_all(workload_summary)
    cv_scatter_html = _fig_to_div(cv_scatter_fig)

    # ---- Ridgeline plot (dropdown-controlled by workload) ----
    ridge_dropdown = _dropdown(
        label="Select workload:",
        select_id="ridge-select",
        prefix="ridge",
        options=[(str(r), f"{WORKLOAD_LABELS[r]} rolls") for r in WORKLOADS],
    )
    ridge_panels = []
    for i, rolls in enumerate(WORKLOADS):
        ridge_fig  = plot_ridgeline(run_table, num_rolls=rolls)
        ridge_html = _fig_to_div(ridge_fig)
        ridge_panels.append(_panel(ridge_html, f"ridge-{rolls}", active=(i == 0)))
    ridge_panels_html = "\n".join(ridge_panels)

    # ---- CV consistency chart (always visible) ----
    cv_fig  = plot_cross_language_consistency(workload_summary)
    cv_html = _fig_to_div(cv_fig)

    # ---- Summary stats table (collapsible) ----
    table_html = _stats_table_html(workload_summary)

    scaling_tip = _chart_tip(
        "Click any language name in the legend to hide/show its line.  "
        "Double-click to isolate one language.  Drag to zoom into a region; "
        "double-click the chart background to reset."
    )

    bar_tip = _chart_tip(
        "Use the dropdown above to switch workload levels.  "
        "Hover over a bar to see the exact mean and standard deviation."
    )

    ridge_tip = _chart_tip(
        "Switch workload levels with the dropdown.  "
        "Wider ridges indicate more timing variability for that language."
    )

    author_cross = _author_note(
        "What stands out to you in the cross-language comparison?  "
        "Is the Python scaling surprise expected?  How do the compiled "
        "languages compare among themselves?  Replace this with your analysis."
    )

    return f"""
<section class="section" id="cross-language">
<h2>4 &mdash; Cross-Language Comparison</h2>

<p>
This section compares all five languages directly.  We start with the
broadest view &mdash; how mean execution time evolves across the full workload
range &mdash; before zooming into individual workload snapshots, distribution
shapes, and dimensionless consistency metrics.
</p>

{cards}

<h3>Scaling Trend</h3>
<p>
The chart below places all five languages on the same log-scaled x-axis,
with a shaded &plusmn;1 standard deviation band around each line.  A narrower
band indicates more consistent timing across repeated trials.
Lines running <em>parallel</em> imply each language shares the same scaling
exponent.  A line that diverges upward signals worse asymptotic behaviour
at large inputs &mdash; most visible for Python at the 1&nbsp;M-roll level.
</p>

{scaling_tip}
{scaling_html}

<h3>Per-Workload Snapshot</h3>
<p>
Use the dropdown to inspect magnitude comparisons at a single fixed
workload.  Bars are sorted by mean execution time in ascending order.
Error bars show &plusmn;1 standard deviation across all trials.
</p>

{bar_tip}
{xwl_dropdown}
{xwl_panels_html}

<h3>Mean Time vs Coefficient of Variation</h3>
<p>
The scatter plot below maps each (language, workload) combination onto
two axes: mean execution time on the x-axis and coefficient of variation
(CV&nbsp;=&nbsp;std&nbsp;/&nbsp;mean) on the y-axis.  Marker size encodes
workload level.  Points in the <em>bottom-left</em> corner are both fast
and consistent &mdash; the ideal outcome.
</p>

{cv_scatter_html}

<h3>Trial Time Distribution (Ridgeline)</h3>
<p>
The ridgeline plot stacks KDE curves for each language vertically so
distribution shapes can be compared at a glance.  Use the dropdown to
switch between workload levels.  A narrow, symmetric ridge indicates
stable timing; a wide or skewed ridge suggests variability.
</p>

{ridge_tip}
{ridge_dropdown}
{ridge_panels_html}

<h3>Timing Consistency (Coefficient of Variation)</h3>
<p>
Raw standard deviation cannot be fairly compared between a language timing
at ~12&nbsp;ms (Rust) and one at ~65&nbsp;ms (Python) &mdash; the absolute
spread naturally differs.  The <strong>coefficient of variation</strong>
(CV&nbsp;=&nbsp;std&nbsp;/&nbsp;mean&nbsp;&times;&nbsp;100&nbsp;%) normalises
spread relative to the mean, making consistency directly comparable.
</p>
<p>
A flat, low CV indicates reliable timing.  A high or climbing CV suggests
the language is susceptible to OS scheduling jitter, JIT warm-up
variability, or memory-pressure effects at that workload level.
</p>

{cv_html}

{author_cross}

<h3>Summary Statistics</h3>
<p>
The full table of descriptive statistics for every (language, workload)
combination is available below.  Expand it for the raw numbers behind the
charts above.
</p>

<details class="collapsible">
<summary>Show full summary statistics table</summary>
<div class="details-body">
{table_html}
</div>
</details>
</section>
"""


def _section_per_language(run_table, workload_summary) -> str:
    """Return the HTML for Section 5: Per-Language Scaling.

    Embeds a top-level language dropdown.  Each language panel contains:
    - Insight cards with key stats for that language.
    - A scaling curve (mean +/- std vs rolls, log x-axis).
    - A nested workload dropdown controlling per-workload trial histograms.
    - An author commentary placeholder.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.

    Returns:
        HTML string for the per-language section.
    """
    ws = add_coefficient_of_variation(workload_summary)

    # Top-level language dropdown.
    lang_dropdown = _dropdown(
        label="Select language:",
        select_id="lang-select",
        prefix="lang",
        options=[(lang, LANGUAGE_DISPLAY[lang]) for lang in LANGUAGES],
    )

    tip = _chart_tip(
        "Select a language from the dropdown to load its charts.  "
        "Within each language, use the workload dropdown to see "
        "individual trial-time histograms.  Hover for exact values."
    )

    # Build one panel per language.
    lang_panels = []
    for i, lang in enumerate(LANGUAGES):
        display = LANGUAGE_DISPLAY[lang]
        color   = LANGUAGE_COLORS[lang]

        # --- Compute per-language stats ---
        lang_ws = ws[ws["language"] == lang].sort_values("rolls")
        small_mean = lang_ws[lang_ws["rolls"] == 100]["mean_ms"].values
        large_mean = lang_ws[lang_ws["rolls"] == 1_000_000]["mean_ms"].values
        small_str  = f"{small_mean[0]:.1f}" if len(small_mean) else "—"
        large_str  = f"{large_mean[0]:.1f}" if len(large_mean) else "—"

        growth = float(large_mean[0]) / float(small_mean[0]) if (len(small_mean) and len(large_mean) and small_mean[0] > 0) else 0
        avg_cv = lang_ws["cv_pct"].mean() if "cv_pct" in lang_ws.columns else 0
        median_all = lang_ws["median_ms"].median()

        lang_cards = _insight_row([
            _insight_card(f"{small_str} ms", "Mean at 100 rolls"),
            _insight_card(f"{large_str} ms", "Mean at 1M rolls"),
            _insight_card(f"{growth:.1f}&times;", "Growth factor (100 &rarr; 1M)"),
            _insight_card(f"{avg_cv:.1f}%", "Avg CV across workloads"),
        ])

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

        lang_author = _author_note(
            f"What surprised you about {display}'s performance profile?  "
            f"Replace this with your observations about {display}."
        )

        lang_content = f"""
<h3>
  <span class="lang-dot" style="background:{color}"></span>
  {display}
</h3>

{lang_cards}

<h4>Scaling Curve</h4>
<p>
  The line below shows how mean elapsed time changes as the workload grows.
  Error bars are &plusmn;1 standard deviation across all trials at that level.
  A nearly flat line indicates sub-linear scaling &mdash; the fixed overhead
  dominates timing at most workload sizes.
</p>
{scale_html}

<h4>Trial Distribution by Workload</h4>
<p>
  Select a workload below to examine the histogram of individual trial
  times.  A tight, symmetric histogram indicates stable timing.
  A long right tail implies occasional outlier runs &mdash; likely from OS
  scheduling preemptions or, in Java&rsquo;s case, JIT compilation events.
</p>
{hist_dropdown}
{hist_panels_html}

{lang_author}
"""
        lang_panels.append(_panel(lang_content, f"lang-{lang}", active=(i == 0)))

    lang_panels_html = "\n".join(lang_panels)

    return f"""
<section class="section" id="per-language">
<h2>5 &mdash; Per-Language Scaling</h2>

<p>
The cross-language view in the previous section shows the <em>relative</em>
picture across all languages at once.  This section zooms into each
language individually, revealing the shape of its scaling curve and the
distribution of individual trial times at each workload level.
</p>

{tip}
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
    2. Loads CSS and JS from ``reports/assets/``.
    3. Builds each of the five HTML sections by calling the section
       builder functions.
    4. Wraps them in a full HTML document shell with inlined CSS and JS.
    5. Writes the finished file to *output_path*, creating the parent
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

    print("[build_report] Loading assets …")
    css = _load_asset("report.css")
    js  = _load_asset("report.js")

    print("[build_report] Building sections …")
    s1 = _section_intro()
    s2 = _section_methodology(batch_table, run_table)
    s3 = _section_batch(batch_table, run_table)
    s4 = _section_cross_language(workload_summary, run_table)
    s5 = _section_per_language(run_table, workload_summary)

    # ---- Assemble the full HTML document ----
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_REPORT_TITLE}</title>
  {_PLOTLY_CDN}
  <style>{css}</style>
</head>
<body>
<div class="report-wrapper">

  <h1>{_REPORT_TITLE}</h1>
  <p class="report-subtitle">
    DiceLab cross-language benchmark &mdash; C++, Go, Java, Python, Rust
  </p>

  {s1}
  <hr class="section-divider">
  {s2}
  <hr class="section-divider">
  {s3}
  <hr class="section-divider">
  {s4}
  <hr class="section-divider">
  {s5}

</div>
<script>{js}</script>
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
