"""Analysis and visualization functions for DiceLab benchmark tables.

This module consumes the three canonical CSV tables produced by
``analysis/run_analysis.py`` (written to ``shared-data/``) and exposes:

1. **Loading helpers** — read each CSV into a typed :class:`pandas.DataFrame`.
2. **Within-language analysis** — how a single language's timing scales with
   workload size, and how consistent individual trials are at each level.
3. **Cross-language analysis** — direct timing comparisons across all
   implementations at each workload level, how those differences evolve as
   roll counts increase, and a relative consistency comparison.
4. **Macro / batch analysis** — how total benchmark batch duration trended
   over repeated batch runs (warm-up, drift, and stability checks).

All plot functions return :class:`plotly.graph_objects.Figure` objects so the
same figure can be embedded in a static HTML report (``fig.to_html()``) or
passed directly to Streamlit (``st.plotly_chart(fig)``) without modification.

Typical usage::

    from pathlib import Path
    from analyze_tables import (
        load_run_table,
        load_workload_summary,
        load_batch_table,
        plot_cross_language_scaling,
        plot_batch_timing_trend,
    )

    run_table       = load_run_table()
    summary         = load_workload_summary()
    batch_table     = load_batch_table()

    fig = plot_cross_language_scaling(summary)
    fig.show()
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default location of the shared-data directory relative to the repo root.
# Override by passing an explicit path to any loading function.
DEFAULT_SHARED_DATA_DIR = Path("shared-data")

# Consistent per-language colors used across every chart so a reader can
# visually track the same language without re-reading the legend each time.
# Values mirror each language's conventional "brand" color where one exists.
LANGUAGE_COLORS: dict[str, str] = {
    "python": "#3572A5",  # Python blue
    "rust": "#DEA584",    # Rust orange
    "go": "#00ADD8",      # Go cyan
    "cpp": "#F34B7D",     # C++ pink-red
    "java": "#B07219",    # Java brown
}

# Human-readable axis tick labels for the five benchmark workload sizes.
# Used wherever roll counts appear on a chart axis.
WORKLOAD_LABELS: dict[int, str] = {
    100: "100",
    1_000: "1 K",
    10_000: "10 K",
    100_000: "100 K",
    1_000_000: "1 M",
}


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_run_table(shared_data_dir: Path = DEFAULT_SHARED_DATA_DIR) -> pd.DataFrame:
    """Load the per-trial run table from ``shared-data/analysis_run_table.csv``.

    Each row represents one timed trial for a specific language, workload, and
    batch run.  This is the most granular table and is the primary source for
    distribution and consistency analysis.

    Columns: ``batch_run_id``, ``language``, ``rolls``, ``sides``,
    ``trial_id``, ``elapsed_ms``.

    Args:
        shared_data_dir: Directory containing the canonical CSV exports.
            Defaults to ``shared-data/`` relative to the current working
            directory (i.e. the repo root).

    Returns:
        DataFrame with ``rolls`` cast to ``int`` and ``elapsed_ms`` to
        ``float`` for safe arithmetic downstream.

    Raises:
        FileNotFoundError: If ``analysis_run_table.csv`` does not exist.
    """
    path = shared_data_dir / "analysis_run_table.csv"
    df = pd.read_csv(path)
    # Explicit casts guard against CSV readers inferring object dtype on
    # columns that happen to contain only numeric strings.
    df["rolls"] = df["rolls"].astype(int)
    df["elapsed_ms"] = df["elapsed_ms"].astype(float)
    return df


def load_batch_table(shared_data_dir: Path = DEFAULT_SHARED_DATA_DIR) -> pd.DataFrame:
    """Load the per-batch timing table from ``shared-data/analysis_batch_table.csv``.

    Each row is one full benchmark batch (all languages × all workloads × all
    trials).  Used for macro-level stability and warm-up analysis.

    Columns: ``run_id``, ``started_at_utc``, ``finished_at_utc``,
    ``elapsed_ms``.

    Args:
        shared_data_dir: Directory containing the canonical CSV exports.

    Returns:
        DataFrame with ``run_id`` cast to ``int`` and ``elapsed_ms`` to
        ``float``.

    Raises:
        FileNotFoundError: If ``analysis_batch_table.csv`` does not exist.
    """
    path = shared_data_dir / "analysis_batch_table.csv"
    df = pd.read_csv(path)
    df["run_id"] = df["run_id"].astype(int)
    df["elapsed_ms"] = df["elapsed_ms"].astype(float)
    return df


def load_workload_summary(shared_data_dir: Path = DEFAULT_SHARED_DATA_DIR) -> pd.DataFrame:
    """Load the aggregated language/workload summary from ``shared-data/``.

    This is a pre-computed summary with one row per (language, rolls, sides)
    combination.  Suitable for cross-language comparisons where per-trial
    granularity is not needed.

    Columns: ``language``, ``rolls``, ``sides``, ``runs``, ``mean_ms``,
    ``median_ms``, ``std_ms``, ``min_ms``, ``max_ms``.

    Args:
        shared_data_dir: Directory containing the canonical CSV exports.

    Returns:
        DataFrame with ``rolls`` cast to ``int``.

    Raises:
        FileNotFoundError: If ``analysis_language_workload_summary.csv`` does
            not exist.
    """
    path = shared_data_dir / "analysis_language_workload_summary.csv"
    df = pd.read_csv(path)
    df["rolls"] = df["rolls"].astype(int)
    return df


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def add_coefficient_of_variation(workload_summary: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *workload_summary* with a ``cv_pct`` column appended.

    Coefficient of variation (CV) = ``(std_ms / mean_ms) × 100``.

    CV is dimensionless, which allows fair consistency comparisons between
    languages with very different mean execution times — for example, Python
    at ~65 ms and Rust at ~12 ms cannot be compared on raw std alone, but
    their CV values are directly comparable.

    A low CV indicates predictable, stable timing.  A high or climbing CV
    suggests external noise, JIT warm-up effects, or OS scheduling variance.

    Args:
        workload_summary: Summary DataFrame from :func:`load_workload_summary`.

    Returns:
        Copy of the input DataFrame with an added ``cv_pct`` (float) column.
        Rows where ``mean_ms`` is zero receive ``NaN`` to avoid division errors.
    """
    out = workload_summary.copy()
    # Replace zero mean with NaN so division produces NaN rather than inf.
    out["cv_pct"] = (out["std_ms"] / out["mean_ms"].replace(0, float("nan"))) * 100
    return out


# ---------------------------------------------------------------------------
# Within-language plots
# ---------------------------------------------------------------------------

def plot_scaling_within_language(
    run_table: pd.DataFrame,
    language: str,
) -> go.Figure:
    """Line chart of mean execution time vs workload size for one language.

    Aggregates all trials across all batch runs for the given language, then
    draws a line through the mean at each roll count.  Error bars show ±1
    standard deviation so trial-to-trial spread is visible alongside the
    underlying scaling trend.

    The x-axis uses a log scale because workloads span four orders of
    magnitude (100 → 1 M), which would compress the small workloads into
    illegibility on a linear scale.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        language: Language identifier to plot (e.g. ``"rust"``).

    Returns:
        Plotly figure with a log-scaled x-axis.
    """
    subset = run_table[run_table["language"] == language].copy()

    # Aggregate over all batch runs and trials for this language at each workload.
    agg = (
        subset.groupby("rolls")["elapsed_ms"]
        .agg(mean_ms="mean", std_ms="std")
        .reset_index()
        .sort_values("rolls")
    )
    # std is NaN when only one sample exists; use 0 so error bars still render.
    agg["std_ms"] = agg["std_ms"].fillna(0)

    color = LANGUAGE_COLORS.get(language, "#888888")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=agg["rolls"],
            y=agg["mean_ms"],
            mode="lines+markers",
            name=language,
            line=dict(color=color, width=2),
            marker=dict(size=8),
            error_y=dict(
                type="data",
                array=agg["std_ms"].tolist(),
                visible=True,
                color=color,
                thickness=1.5,
            ),
            hovertemplate=(
                "Rolls: %{x:,}<br>"
                "Mean: %{y:.2f} ms<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Execution Time Scaling — {language}",
        xaxis=dict(
            title="Rolls per simulation",
            type="log",
            # Pin tick positions to the exact workload levels so the axis is
            # not cluttered with intermediate values Plotly might choose.
            tickvals=sorted(WORKLOAD_LABELS.keys()),
            ticktext=[WORKLOAD_LABELS[r] for r in sorted(WORKLOAD_LABELS.keys())],
        ),
        yaxis=dict(title="Mean elapsed time (ms)"),
        template="plotly_white",
        showlegend=False,
    )
    return fig


def plot_trial_histogram_within_language(
    run_table: pd.DataFrame,
    language: str,
    rolls: int,
) -> go.Figure:
    """Histogram of individual trial times for one language at one workload level.

    Useful for inspecting the *shape* of the timing distribution at a specific
    (language, roll count) combination — whether it is symmetric, right-skewed
    from occasional OS interruptions, or bimodal from JIT warm-up effects.

    Call this once per workload level of interest to build a set of
    distribution snapshots for the language under review.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        language: Language identifier to plot.
        rolls: Roll count to isolate (must exist in the table, e.g. ``100000``).

    Returns:
        Plotly histogram figure.
    """
    subset = run_table[
        (run_table["language"] == language) & (run_table["rolls"] == rolls)
    ]

    color = LANGUAGE_COLORS.get(language, "#888888")
    label = WORKLOAD_LABELS.get(rolls, str(rolls))

    fig = px.histogram(
        subset,
        x="elapsed_ms",
        nbins=20,
        title=f"Trial Time Distribution — {language} at {label} rolls",
        color_discrete_sequence=[color],
        template="plotly_white",
    )
    fig.update_layout(
        xaxis_title="Elapsed time (ms)",
        yaxis_title="Trial count",
        bargap=0.05,
    )
    return fig


# ---------------------------------------------------------------------------
# Cross-language plots
# ---------------------------------------------------------------------------

def plot_cross_language_scaling(workload_summary: pd.DataFrame) -> go.Figure:
    """Multi-line chart comparing mean execution time vs rolls across all languages.

    Each language gets its own line using the consistent color palette.  The
    log-scaled x-axis makes it easy to see both the absolute performance gaps
    and whether those gaps widen, narrow, or stay parallel as workload grows.

    Lines running parallel on a log-x axis imply the languages share the same
    scaling exponent.  A line that rises faster than others signals worse
    asymptotic scaling for large workloads.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.

    Returns:
        Plotly figure with one line per language.
    """
    fig = go.Figure()

    for language in sorted(workload_summary["language"].unique()):
        lang_df = workload_summary[workload_summary["language"] == language].sort_values("rolls")
        color = LANGUAGE_COLORS.get(language, "#888888")

        fig.add_trace(
            go.Scatter(
                x=lang_df["rolls"],
                y=lang_df["mean_ms"],
                mode="lines+markers",
                name=language,
                line=dict(color=color, width=2),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{language}</b><br>"
                    "Rolls: %{x:,}<br>"
                    "Mean: %{y:.2f} ms<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Execution Time Scaling — All Languages",
        xaxis=dict(
            title="Rolls per simulation",
            type="log",
            tickvals=sorted(WORKLOAD_LABELS.keys()),
            ticktext=[WORKLOAD_LABELS[r] for r in sorted(WORKLOAD_LABELS.keys())],
        ),
        yaxis=dict(title="Mean elapsed time (ms)"),
        legend=dict(title="Language"),
        template="plotly_white",
    )
    return fig


def plot_cross_language_at_workload(
    workload_summary: pd.DataFrame,
    rolls: int,
) -> go.Figure:
    """Bar chart comparing mean timing across all languages at a fixed roll count.

    Error bars show ±1 standard deviation.  Call this once per workload level
    to build a series of snapshots showing how the relative performance gap
    looks at each simulation size.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.
        rolls: Roll count to slice (must exist in the summary table).

    Returns:
        Plotly bar chart figure.
    """
    subset = workload_summary[workload_summary["rolls"] == rolls].sort_values("language")
    label = WORKLOAD_LABELS.get(rolls, str(rolls))

    # Build a color list aligned with the sorted language order.
    colors = [LANGUAGE_COLORS.get(lang, "#888888") for lang in subset["language"]]

    fig = go.Figure(
        go.Bar(
            x=subset["language"],
            y=subset["mean_ms"],
            error_y=dict(
                type="data",
                array=subset["std_ms"].tolist(),
                visible=True,
            ),
            marker_color=colors,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Mean: %{y:.2f} ms<br>"
                "Std: %{error_y.array:.2f} ms<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Cross-Language Timing Comparison — {label} rolls",
        xaxis_title="Language",
        yaxis_title="Mean elapsed time (ms)",
        template="plotly_white",
        showlegend=False,
    )
    return fig


def plot_cross_language_consistency(workload_summary: pd.DataFrame) -> go.Figure:
    """Multi-line chart of coefficient of variation (CV) vs rolls for all languages.

    CV = std / mean × 100 %.  Being dimensionless, it levels the field between
    fast languages (Rust at ~12 ms) and slow ones (Python at ~65 ms), allowing
    a direct comparison of *relative* timing consistency rather than absolute
    spread.

    A flat, low CV line means timing is stable and predictable.  A high or
    rising CV line suggests susceptibility to OS scheduling noise, JIT
    warm-up effects, or memory pressure.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.

    Returns:
        Plotly figure with one CV line per language.
    """
    # CV is not stored in the CSV; compute it before plotting.
    df = add_coefficient_of_variation(workload_summary)

    fig = go.Figure()

    for language in sorted(df["language"].unique()):
        lang_df = df[df["language"] == language].sort_values("rolls")
        color = LANGUAGE_COLORS.get(language, "#888888")

        fig.add_trace(
            go.Scatter(
                x=lang_df["rolls"],
                y=lang_df["cv_pct"],
                mode="lines+markers",
                name=language,
                line=dict(color=color, width=2),
                marker=dict(size=7),
                hovertemplate=(
                    f"<b>{language}</b><br>"
                    "Rolls: %{x:,}<br>"
                    "CV: %{y:.1f}%<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Timing Consistency (CV) — All Languages",
        xaxis=dict(
            title="Rolls per simulation",
            type="log",
            tickvals=sorted(WORKLOAD_LABELS.keys()),
            ticktext=[WORKLOAD_LABELS[r] for r in sorted(WORKLOAD_LABELS.keys())],
        ),
        yaxis=dict(title="Coefficient of variation (%)"),
        legend=dict(title="Language"),
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------
# Macro / batch plots
# ---------------------------------------------------------------------------

def plot_batch_timing_trend(batch_table: pd.DataFrame) -> go.Figure:
    """Line chart of total batch elapsed time across sequential batch runs.

    Each point is one full benchmark pass (all languages × all workloads ×
    all trials).  A downward trend at the start is typical warm-up behaviour
    (CPU branch predictors, file system caches, JVM JIT).  A rising trend or
    high variance later can indicate sustained system load or thermal
    throttling during the session.

    Args:
        batch_table: Per-batch DataFrame from :func:`load_batch_table`.

    Returns:
        Plotly line chart with batch ``run_id`` on the x-axis and total
        elapsed time in ms on the y-axis.
    """
    df = batch_table.sort_values("run_id")

    fig = go.Figure(
        go.Scatter(
            x=df["run_id"],
            y=df["elapsed_ms"],
            mode="lines+markers",
            line=dict(color="#5C6BC0", width=2),
            marker=dict(size=8),
            hovertemplate=(
                "Batch %{x}<br>"
                "Elapsed: %{y:.1f} ms<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Batch Timing Trend Across Benchmark Runs",
        xaxis=dict(
            title="Batch run index",
            # Integer batch IDs; step by 1 so every batch is labelled.
            tickmode="linear",
            dtick=1,
        ),
        yaxis=dict(title="Total batch elapsed time (ms)"),
        template="plotly_white",
        showlegend=False,
    )
    return fig
