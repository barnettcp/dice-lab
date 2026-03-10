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

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import gaussian_kde


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
# Human-readable display names for each language.
LANGUAGE_DISPLAY: dict[str, str] = {
    "cpp":    "C++",
    "go":     "Go",
    "java":   "Java",
    "python": "Python",
    "rust":   "Rust",
}

WORKLOAD_LABELS: dict[int, str] = {
    100: "100",
    1_000: "1 K",
    10_000: "10 K",
    100_000: "100 K",
    1_000_000: "1 M",
}

# Discrete marker sizes per workload for bubble-style scatter plots.
WORKLOAD_SIZES: dict[int, int] = {
    100:       6,
    1_000:     9,
    10_000:    13,
    100_000:   18,
    1_000_000: 24,
}

# Canonical ordered lists for iteration.
LANGUAGES: list[str] = ["cpp", "go", "java", "python", "rust"]
WORKLOADS: list[int] = [100, 1_000, 10_000, 100_000, 1_000_000]


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
    subset = workload_summary[workload_summary["rolls"] == rolls].sort_values("mean_ms")
    label = WORKLOAD_LABELS.get(rolls, str(rolls))

    # Build a color list aligned with the sorted order.
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

def plot_batch_timing_trend(
    batch_table: pd.DataFrame,
    gridline_alpha: float = 0.15,
    window: int = 10,
) -> go.Figure:
    """Line chart of total batch elapsed time across sequential batch runs.

    Each point is one full benchmark pass (all languages × all workloads ×
    all trials).  A downward trend at the start is typical warm-up behaviour
    (CPU branch predictors, file system caches, JVM JIT).  A rising trend or
    high variance later can indicate sustained system load or thermal
    throttling during the session.

    A rolling mean (MA) overlay and ±1 standard deviation band are drawn to
    separate trend from noise.  The first ``window - 1`` points of the rolling
    calculations are ``NaN`` and are simply omitted from those traces.

    Args:
        batch_table: Per-batch DataFrame from :func:`load_batch_table`.
        gridline_alpha: Opacity of the vertical reference lines drawn at every
            10th batch run (0.0 = invisible, 1.0 = fully opaque).
        window: Rolling window size for the mean and std deviation overlay.
            Use 5 for a more reactive line, 10 for a smoother trend.

    Returns:
        Plotly line chart with batch ``run_id`` on the x-axis and total
        elapsed time in ms on the y-axis.
    """
    df = batch_table.sort_values("run_id").copy()

    # Compute rolling statistics (min_periods=window to avoid partial windows)
    df["roll_mean"] = df["elapsed_ms"].rolling(window, min_periods=window).mean()
    df["roll_std"]  = df["elapsed_ms"].rolling(window, min_periods=window).std()
    df["band_upper"] = df["roll_mean"] + df["roll_std"]
    df["band_lower"] = df["roll_mean"] - df["roll_std"]

    fig = go.Figure()

    # ── ±1 std deviation band ───────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df["run_id"], y=df["band_upper"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=df["run_id"], y=df["band_lower"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(255, 165, 0, 0.15)",
        name=f"±1 std (MA{window})",
        showlegend=True,
        hoverinfo="skip",
    ))

    # ── Raw data ────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df["run_id"],
        y=df["elapsed_ms"],
        mode="lines+markers",
        line=dict(color="#5C6BC0", width=1.5),
        marker=dict(size=6),
        name="Batch elapsed (ms)",
        hovertemplate=(
            "Batch %{x}<br>"
            "Elapsed: %{y:.1f} ms<extra></extra>"
        ),
    ))

    # ── Rolling mean overlay ─────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df["run_id"],
        y=df["roll_mean"],
        mode="lines",
        line=dict(color="rgba(230, 100, 0, 0.85)", width=2.5, dash="solid"),
        name=f"MA({window})",
        hovertemplate=(
            f"MA({window}) at batch %{{x}}<br>"
            "Mean: %{y:.1f} ms<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=(
            f"Batch Timing Trend Across Benchmark Runs (MA{window} overlay)"
            "<br>Each point is one full batch of experiments "
            "(all languages × workloads × trials)"
        ),
        xaxis=dict(
            title="Batch run index",
            tickmode="linear",
            dtick=10,
            gridcolor=f"rgba(0,0,0,{gridline_alpha})",
        ),
        yaxis=dict(title="Total batch elapsed time (ms)"),
        template="plotly_white",
        legend=dict(
            orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5,
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def hex_to_rgba(hex_color: str, alpha: float = 0.55) -> str:
    """Convert a hex colour string to an ``rgba()`` CSS value.

    Args:
        hex_color: A CSS hex colour such as ``"#3572A5"`` or ``"#DEA584"``.
        alpha: Opacity component (0.0 = fully transparent, 1.0 = fully opaque).

    Returns:
        An ``rgba(r, g, b, a)`` string suitable for Plotly ``fillcolor`` and
        similar properties.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _filter_iqr(df: pd.DataFrame) -> pd.DataFrame:
    """Return *df* with rows outside 1.5×IQR fences removed per language × workload.

    Used by :func:`plot_boxwhisker_by_workload` to clip whiskers to the
    standard 1.5×IQR range without rendering individual outlier points.

    Args:
        df: A subset of the run table containing at least ``language``,
            ``rolls``, and ``elapsed_ms`` columns.

    Returns:
        Filtered DataFrame containing only rows within the IQR fences.
    """
    kept = []
    for _, group in df.groupby(["language", "rolls"]):
        q1 = group["elapsed_ms"].quantile(0.25)
        q3 = group["elapsed_ms"].quantile(0.75)
        iqr = q3 - q1
        mask = group["elapsed_ms"].between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
        kept.append(group[mask])
    return pd.concat(kept)


# ---------------------------------------------------------------------------
# Cross-language scatter / distribution plots
# ---------------------------------------------------------------------------

def plot_mean_vs_cv_all(
    workload_summary: pd.DataFrame,
    size_legend: bool = False,
) -> go.Figure:
    """Scatter plot of mean execution time vs coefficient of variation.

    Each point represents one (language, workload) combination.  Marker colour
    encodes language and marker size encodes workload level, giving a
    two-dimensional overview of both absolute performance and relative
    consistency in a single chart.

    The language legend is fully interactive (click to toggle).  The optional
    workload-size legend is a visual reference only — clicking it hides the
    legend entry but does not filter chart data, because Plotly does not
    support two independent clickable legend dimensions on one chart.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.  Must contain ``mean_ms`` and
            ``std_ms`` columns; CV is computed internally.
        size_legend: If ``True``, append grey dummy markers showing the
            workload-size scale in the legend.

    Returns:
        Plotly figure with language-coloured, workload-sized markers.
    """
    df = workload_summary.copy()
    df["cv"] = df["std_ms"] / df["mean_ms"].replace(0, float("nan"))

    fig = go.Figure()

    for i, lang in enumerate(LANGUAGES):
        sub = df[df["language"] == lang].copy()
        if sub.empty:
            continue

        sub["marker_size"] = sub["rolls"].map(WORKLOAD_SIZES)
        sub["workload_label"] = sub["rolls"].map(WORKLOAD_LABELS)

        fig.add_trace(go.Scatter(
            x=sub["mean_ms"],
            y=sub["cv"],
            mode="markers",
            name=LANGUAGE_DISPLAY.get(lang, lang),
            legendgroup=f"lang_{lang}",
            legendgrouptitle_text="Language" if i == 0 else None,
            showlegend=True,
            marker=dict(
                color=LANGUAGE_COLORS[lang],
                size=sub["marker_size"],
                line=dict(width=0.5, color="white"),
            ),
            customdata=sub["workload_label"],
            hovertemplate=(
                f"<b>{LANGUAGE_DISPLAY.get(lang, lang)}</b><br>"
                "Workload: %{customdata}<br>"
                "Mean: %{x:.5f} ms<br>"
                "CV: %{y:.4f}"
                "<extra></extra>"
            ),
        ))

    if size_legend:
        for i, workload in enumerate(WORKLOADS):
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                name=WORKLOAD_LABELS[workload],
                legendgrouptitle_text="Workload (Rolls)" if i == 0 else None,
                legendgroup="workload_size_legend",
                showlegend=True,
                marker=dict(
                    color="gray",
                    size=WORKLOAD_SIZES[workload],
                ),
            ))

    fig.update_layout(
        title="Mean Roll Time vs Coefficient of Variance by Language and Workload",
        xaxis_title="Mean Roll Time (ms)",
        yaxis_title="Coefficient of Variance",
        legend=dict(groupclick="toggleitem"),
        template="plotly_white",
    )
    return fig


def plot_histogram_and_kde(
    run_table: pd.DataFrame,
    num_rolls: int = 100_000,
    show_bars: bool = True,
) -> go.Figure:
    """Overlaid histograms and KDE curves of elapsed time for all languages.

    Useful for comparing the *shape* of each language's timing distribution
    at a single workload level — whether distributions are tight or spread,
    symmetric or skewed, and how much they overlap.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        num_rolls: Workload level to isolate (e.g. ``100_000``).
        show_bars: If ``True``, render semi-transparent histogram bars behind
            the KDE lines.  Set to ``False`` for a cleaner KDE-only view.

    Returns:
        Plotly figure with one histogram and/or KDE trace per language.
    """
    work_df = run_table[run_table["rolls"] == num_rolls]
    fig = go.Figure()

    for lang in LANGUAGES:
        lang_df = work_df[work_df["language"] == lang]
        data = lang_df["elapsed_ms"]
        color = LANGUAGE_COLORS.get(lang, None)

        if show_bars:
            fig.add_trace(go.Histogram(
                x=data,
                name=LANGUAGE_DISPLAY.get(lang, lang),
                marker_color=color,
                opacity=0.5,
                nbinsx=30,
                histnorm="probability density",
                showlegend=True,
            ))

        if len(data) > 1:
            kde = gaussian_kde(data)
            x_grid = np.linspace(data.min(), data.max(), 200)
            fig.add_trace(go.Scatter(
                x=x_grid,
                y=kde(x_grid),
                mode="lines",
                name=f"{LANGUAGE_DISPLAY.get(lang, lang)} KDE",
                line=dict(color=color, width=2, dash="solid"),
                fill="tozeroy",
                showlegend=True,
            ))

    fig.update_layout(
        title=f"Elapsed Time Distribution by Language<br>(Workload: {num_rolls:,} rolls)",
        xaxis_title="Elapsed Time (ms)",
        yaxis_title="Density",
        barmode="overlay",
        legend_title="Language",
        template="plotly_white",
    )
    return fig


def plot_ridgeline(
    run_table: pd.DataFrame,
    num_rolls: int = 100_000,
    overlap: float = 0.75,
    baseline_alpha: float = 0.25,
) -> go.Figure:
    """Ridgeline (joy) plot of elapsed time KDE distributions per language.

    Each language sits on its own horizontal baseline.  Peaks taller than the
    row spacing visually overflow into the band above, producing a layered
    3-D feel that makes it easy to compare distribution shapes at a glance.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        num_rolls: Workload level to isolate (e.g. ``100_000``).
        overlap: Controls how much peaks bleed into the row above.
            ``0`` = fully separated rows, ``1`` = baselines at the same
            level (total overlap).  Values around 0.5–0.75 work well.
        baseline_alpha: Opacity of the per-language baseline reference
            lines (0.0–1.0).

    Returns:
        Plotly figure with one KDE ridge per language, stacked vertically.
    """
    work_df = run_table[run_table["rolls"] == num_rolls]

    kdes: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for lang in LANGUAGES:
        data = work_df[work_df["language"] == lang]["elapsed_ms"].dropna()
        if len(data) < 2:
            continue
        kde = gaussian_kde(data)
        x_grid = np.linspace(data.min(), data.max(), 400)
        kdes[lang] = (x_grid, kde(x_grid))

    if not kdes:
        fig = go.Figure()
        fig.update_layout(title="No data to plot.")
        return fig

    max_kde_height = max(y.max() for _, y in kdes.values())
    spacing = max_kde_height * (1.0 - overlap)

    all_x = np.concatenate([x for x, _ in kdes.values()])
    x_min, x_max = all_x.min(), all_x.max()

    fig = go.Figure()

    for lang in reversed(LANGUAGES):
        if lang not in kdes:
            continue
        idx = LANGUAGES.index(lang)
        baseline = idx * spacing
        x_grid, y_kde = kdes[lang]
        color = LANGUAGE_COLORS.get(lang, "#888888")

        fig.add_trace(go.Scatter(
            x=[x_min, x_max],
            y=[baseline, baseline],
            mode="lines",
            line=dict(color=hex_to_rgba(color, alpha=baseline_alpha), width=1),
            showlegend=False,
            hoverinfo="skip",
        ))

        x_poly = np.concatenate([[x_grid[0]], x_grid, [x_grid[-1]]])
        y_base = np.full(len(x_poly), baseline)
        y_top  = np.concatenate([[baseline], y_kde + baseline, [baseline]])

        fig.add_trace(go.Scatter(
            x=x_poly, y=y_base,
            mode="lines",
            line=dict(color="rgba(0,0,0,0)", width=0),
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=x_poly, y=y_top,
            mode="lines",
            fill="tonexty",
            fillcolor=hex_to_rgba(color, alpha=0.55),
            line=dict(color=color, width=2),
            name=LANGUAGE_DISPLAY.get(lang, lang),
            showlegend=True,
            hovertemplate=(
                f"<b>{LANGUAGE_DISPLAY.get(lang, lang)}</b><br>"
                "Time: %{x:.4f} ms"
                "<extra></extra>"
            ),
        ))

    active_langs = [l for l in LANGUAGES if l in kdes]
    fig.update_layout(
        title=f"Elapsed Time Ridgeline by Language<br>(Workload: {num_rolls:,} rolls)",
        xaxis_title="Elapsed Time (ms)",
        yaxis=dict(
            tickvals=[LANGUAGES.index(l) * spacing for l in active_langs],
            ticktext=[LANGUAGE_DISPLAY.get(l, l) for l in active_langs],
            showgrid=False,
            zeroline=False,
        ),
        legend_title="Language",
        template="plotly_white",
        hovermode="x unified",
    )
    return fig


def plot_mean_time_by_workload(workload_summary: pd.DataFrame) -> go.Figure:
    """Multi-line chart of mean elapsed time vs workload with ±1 std band.

    Each language is drawn as a line with markers, accompanied by a
    semi-transparent shaded band showing ±1 standard deviation.  A narrower
    band indicates more consistent timing across trials.

    The x-axis is log-scaled because workloads span four orders of magnitude
    (100 → 1 M), which would compress small workloads on a linear scale.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.  Must contain ``mean_ms``,
            ``std_ms``, and ``rolls`` columns.  A ``cv`` column is used in
            hover if present; otherwise it is computed on the fly.

    Returns:
        Plotly figure with one line + band per language.
    """
    df = workload_summary.copy()
    if "cv" not in df.columns:
        df["cv"] = df["std_ms"] / df["mean_ms"].replace(0, float("nan"))

    fig = go.Figure()

    for lang in LANGUAGES:
        sub = df[df["language"] == lang].sort_values("rolls")
        if sub.empty:
            continue

        color = LANGUAGE_COLORS[lang]
        display = LANGUAGE_DISPLAY.get(lang, lang)

        upper = sub["mean_ms"] + sub["std_ms"]
        lower = sub["mean_ms"] - sub["std_ms"]

        fig.add_trace(go.Scatter(
            x=sub["rolls"], y=upper,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
            legendgroup=lang,
        ))
        fig.add_trace(go.Scatter(
            x=sub["rolls"], y=lower,
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor=hex_to_rgba(color, alpha=0.15),
            showlegend=False,
            hoverinfo="skip",
            legendgroup=lang,
        ))

        fig.add_trace(go.Scatter(
            x=sub["rolls"],
            y=sub["mean_ms"],
            mode="lines+markers",
            name=display,
            legendgroup=lang,
            line=dict(color=color, width=2),
            marker=dict(size=7),
            customdata=sub[["std_ms", "cv"]].values,
            hovertemplate=(
                f"<b>{display}</b><br>"
                "Rolls: %{x:,}<br>"
                "Mean: %{y:.4f} ms<br>"
                "Std: %{customdata[0]:.4f} ms<br>"
                "CV: %{customdata[1]:.4f}"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=(
            "Mean Roll Time by Workload Size per Language"
            "<br><sup>Shaded band = ±1 std deviation (consistency); "
            "narrower band = more consistent</sup>"
        ),
        xaxis=dict(
            title="Workload (rolls per trial)",
            type="log",
            tickvals=WORKLOADS,
            ticktext=[WORKLOAD_LABELS[w] for w in WORKLOADS],
        ),
        yaxis=dict(title="Mean elapsed time (ms)"),
        template="plotly_white",
        legend_title="Language",
    )
    return fig


def plot_normalized_scaling(
    workload_summary: pd.DataFrame,
    baseline_rolls: int = 10_000,
) -> go.Figure:
    """Normalised scaling chart relative to each language's own baseline.

    Every language reads ``1.0`` at *baseline_rolls*, so the chart shows
    *how fast or slow each language scales* rather than absolute speed.  A
    line rising steeply to the right means that language scales poorly with
    load.  A flat line means near-linear scaling.

    Args:
        workload_summary: Aggregated summary DataFrame from
            :func:`load_workload_summary`.
        baseline_rolls: The workload level used as the normalisation
            reference (default ``10_000``).

    Returns:
        Plotly figure with one normalised line + band per language and a
        dashed reference line at ``y = 1``.
    """
    fig = go.Figure()

    for lang in LANGUAGES:
        sub = workload_summary[workload_summary["language"] == lang].sort_values("rolls").copy()
        if sub.empty:
            continue

        baseline_row = sub[sub["rolls"] == baseline_rolls]
        if baseline_row.empty:
            continue

        baseline_mean = baseline_row["mean_ms"].values[0]

        sub["norm_mean"]  = sub["mean_ms"] / baseline_mean
        sub["norm_std"]   = sub["std_ms"] / baseline_mean
        sub["norm_upper"] = sub["norm_mean"] + sub["norm_std"]
        sub["norm_lower"] = sub["norm_mean"] - sub["norm_std"]

        color   = LANGUAGE_COLORS[lang]
        display = LANGUAGE_DISPLAY.get(lang, lang)

        fig.add_trace(go.Scatter(
            x=sub["rolls"], y=sub["norm_upper"],
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
            legendgroup=lang,
        ))
        fig.add_trace(go.Scatter(
            x=sub["rolls"], y=sub["norm_lower"],
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor=hex_to_rgba(color, alpha=0.15),
            showlegend=False, hoverinfo="skip",
            legendgroup=lang,
        ))

        fig.add_trace(go.Scatter(
            x=sub["rolls"],
            y=sub["norm_mean"],
            mode="lines+markers",
            name=display,
            legendgroup=lang,
            line=dict(color=color, width=2),
            marker=dict(size=7),
            customdata=sub[["mean_ms", "norm_std"]].values,
            hovertemplate=(
                f"<b>{display}</b><br>"
                "Rolls: %{x:,}<br>"
                "Scaled mean: %{y:.3f}×<br>"
                "Actual mean: %{customdata[0]:.4f} ms"
                "<extra></extra>"
            ),
        ))

    fig.add_hline(
        y=1.0,
        line=dict(color="rgba(0,0,0,0.25)", width=1, dash="dot"),
        annotation_text=f"Baseline ({WORKLOAD_LABELS[baseline_rolls]} rolls = 1×)",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title=(
            f"Scaling Relative to {WORKLOAD_LABELS[baseline_rolls]}-Roll Baseline"
            "<br><sup>1.0 = each language's own time at the baseline workload; "
            "steeper slope = worse scaling</sup>"
        ),
        xaxis=dict(
            title="Workload (rolls per trial)",
            type="log",
            tickvals=WORKLOADS,
            ticktext=[WORKLOAD_LABELS[w] for w in WORKLOADS],
        ),
        yaxis=dict(
            title=f"Mean time relative to {WORKLOAD_LABELS[baseline_rolls]}-roll baseline (×)",
        ),
        template="plotly_white",
        legend_title="Language",
    )
    return fig


def plot_boxwhisker_by_workload(
    run_table: pd.DataFrame,
    language: str | None = None,
) -> go.Figure:
    """Box-and-whisker plot of elapsed time by workload and language.

    Uses all individual trial observations from the run table to compute full
    distributions.  Workloads appear on the x-axis; each language gets its own
    coloured box within each workload group for a side-by-side comparison of
    both absolute performance and spread.

    Outliers beyond 1.5×IQR are pre-filtered so that whiskers represent the
    standard IQR fences without extreme values distorting the axis.

    Args:
        run_table: Per-trial DataFrame from :func:`load_run_table`.
        language: If provided, restrict the chart to a single language
            (e.g. ``"python"``).  When ``None``, all languages are shown
            side-by-side.

    Returns:
        Plotly figure with grouped box traces.

    Raises:
        ValueError: If *language* is not in :data:`LANGUAGES`.
    """
    if language is not None and language not in LANGUAGES:
        raise ValueError(f"Unknown language '{language}'. Choose from: {LANGUAGES}")

    langs_to_plot = [language] if language is not None else LANGUAGES
    df_filtered = _filter_iqr(run_table[run_table["language"].isin(langs_to_plot)])

    fig = go.Figure()

    for lang in langs_to_plot:
        sub = df_filtered[df_filtered["language"] == lang]
        if sub.empty:
            continue

        color   = LANGUAGE_COLORS[lang]
        display = LANGUAGE_DISPLAY.get(lang, lang)
        x_labels = sub["rolls"].map(WORKLOAD_LABELS)

        fig.add_trace(go.Box(
            x=x_labels,
            y=sub["elapsed_ms"],
            name=display,
            marker_color=color,
            line_color=color,
            fillcolor=hex_to_rgba(color, alpha=0.4),
            boxmean="sd",
            boxpoints=False,
            legendgroup=lang,
            hovertemplate=(
                f"<b>{display}</b><br>"
                "Workload: %{x}<br>"
                "Elapsed: %{y:.4f} ms"
                "<extra></extra>"
            ),
        ))

    ordered_labels = [WORKLOAD_LABELS[w] for w in WORKLOADS]

    if language is not None:
        title_main = f"Elapsed Time Distribution — {LANGUAGE_DISPLAY.get(language, language)}"
    else:
        title_main = "Elapsed Time Distribution by Language and Workload"

    fig.update_layout(
        title=(
            title_main
            + "<br><sup>Box = IQR · whiskers = 1.5×IQR · diamond = "
            "mean ± 1 std · outliers excluded</sup>"
        ),
        xaxis=dict(
            title="Workload (rolls per trial)",
            categoryorder="array",
            categoryarray=ordered_labels,
        ),
        yaxis=dict(title="Elapsed time (ms)"),
        boxmode="group",
        template="plotly_white",
        legend_title="Language",
    )
    return fig
