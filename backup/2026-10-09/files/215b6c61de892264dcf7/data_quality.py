"""
Data quality diagnostics for the intermarket thesis dataset.

Provides per-ticker statistics (missing values, gaps, outliers, distributional
properties) and cross-ticker coverage overlap checks.  All functions are
standalone — they read from a DataFrame and write nothing to disk unless
explicitly asked.

Typical usage
-------------
    from thesis_app.data_quality import run_data_quality_report
    prices = pd.read_csv("data/raw/prices.csv", index_col=0, parse_dates=True)
    report = run_data_quality_report(prices, output_dir="outputs/tables")
"""
from __future__ import annotations

import os
import warnings
from typing import Dict, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Core per-ticker statistics
# ---------------------------------------------------------------------------

def ticker_quality_stats(prices: pd.DataFrame, sigma_threshold: float = 5.0) -> pd.DataFrame:
    """Return a DataFrame with one row per ticker summarising data quality.

    Columns
    -------
    first_date, last_date, n_obs         : coverage info
    n_missing_price                      : NaN price cells
    n_gaps_1d, n_gaps_2d, n_gaps_gt2d    : consecutive calendar-day price gaps
    n_zero_returns                        : log-return exactly 0 (potential fill artefact)
    n_outlier_returns                     : |z-score| > sigma_threshold
    skewness, excess_kurtosis            : distribution shape
    annualised_vol_pct                   : σ of log-returns × √252 × 100
    pct_missing                          : n_missing_price / total_calendar_days × 100
    """
    rows = []
    returns = np.log(prices / prices.shift(1))

    for ticker in prices.columns:
        px = prices[ticker].dropna()
        if px.empty:
            rows.append({"ticker": ticker, "note": "ALL MISSING"})
            continue

        ret = returns[ticker].dropna()
        full_range = pd.date_range(px.index.min(), px.index.max(), freq="D")
        n_calendar = len(full_range)
        n_missing_price = int(prices[ticker].isna().sum())

        # Gap analysis on calendar days between consecutive observations
        diffs = pd.Series(px.index).diff().dropna().dt.days
        n_gaps_1d = int((diffs == 1).sum())
        n_gaps_2d = int((diffs == 2).sum())
        n_gaps_gt2d = int((diffs > 2).sum())

        n_zero_returns = int((ret == 0).sum())

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if len(ret) > 3:
                z_scores = (ret - ret.mean()) / (ret.std() + 1e-15)
                n_outliers = int((z_scores.abs() > sigma_threshold).sum())
                skew = float(ret.skew())
                kurt = float(ret.kurt())   # excess (Fisher)
            else:
                n_outliers = skew = kurt = np.nan

        ann_vol = float(ret.std() * np.sqrt(252) * 100) if len(ret) > 1 else np.nan

        rows.append({
            "ticker": ticker,
            "first_date": px.index.min().date(),
            "last_date": px.index.max().date(),
            "n_obs": len(px),
            "n_calendar_days": n_calendar,
            "pct_missing": round(n_missing_price / max(n_calendar, 1) * 100, 2),
            "n_missing_price": n_missing_price,
            "n_gaps_1d": n_gaps_1d,
            "n_gaps_2d": n_gaps_2d,
            "n_gaps_gt2d": n_gaps_gt2d,
            "n_zero_returns": n_zero_returns,
            f"n_outliers_{sigma_threshold:.0f}s": n_outliers,
            "skewness": round(skew, 3) if not np.isnan(skew) else np.nan,
            "excess_kurtosis": round(kurt, 3) if not np.isnan(kurt) else np.nan,
            "annualised_vol_pct": round(ann_vol, 2) if not np.isnan(ann_vol) else np.nan,
        })

    return pd.DataFrame(rows).set_index("ticker")


def check_coverage_overlap(prices: pd.DataFrame) -> pd.DataFrame:
    """Pairwise overlap matrix: number of days both tickers have non-NaN prices."""
    tickers = list(prices.columns)
    mat = np.zeros((len(tickers), len(tickers)), dtype=int)
    for i, a in enumerate(tickers):
        for j, b in enumerate(tickers):
            mat[i, j] = int((prices[a].notna() & prices[b].notna()).sum())
    return pd.DataFrame(mat, index=tickers, columns=tickers)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def plot_missing_heatmap(prices: pd.DataFrame, output_path: Optional[str] = None):
    """Binary heatmap of missing prices — white = present, black = missing."""
    fig, ax = plt.subplots(figsize=(14, 4))
    mask = prices.isna().T.astype(int)
    ax.imshow(mask, aspect="auto", cmap="Greys", interpolation="nearest")
    ax.set_yticks(range(len(prices.columns)))
    ax.set_yticklabels(prices.columns, fontsize=10)
    n = len(prices)
    step = max(1, n // 8)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels(
        [str(d.date()) for d in prices.index[::step]], rotation=45, ha="right", fontsize=8
    )
    ax.set_title("Missing price data (black = missing)", fontweight="bold")
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return fig


def plot_return_outliers(
    returns: pd.DataFrame,
    sigma_threshold: float = 5.0,
    output_path: Optional[str] = None,
):
    """Time-series plot highlighting extreme return observations per ticker."""
    tickers = list(returns.columns)
    ncols = 2
    nrows = (len(tickers) + 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 3 * nrows), sharex=True)
    axes_flat = np.array(axes).flatten()

    for idx, ticker in enumerate(tickers):
        ax = axes_flat[idx]
        ret = returns[ticker].dropna()
        ax.plot(ret.index, ret.values, color="steelblue", linewidth=0.6, alpha=0.8)
        mu, sigma = ret.mean(), ret.std()
        outlier_mask = (ret - mu).abs() > sigma_threshold * sigma
        ax.scatter(
            ret.index[outlier_mask], ret.values[outlier_mask],
            color="crimson", s=20, zorder=5, label=f"|z|>{sigma_threshold:.0f}σ"
        )
        ax.axhline(0, color="black", linewidth=0.4)
        ax.set_title(ticker, fontsize=11, fontweight="bold")
        ax.set_ylabel("Log return")
        if outlier_mask.any():
            ax.legend(fontsize=8, loc="lower right")

    for idx in range(len(tickers), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle(f"Log returns with {sigma_threshold:.0f}σ outliers highlighted", y=1.01, fontweight="bold")
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return fig


def plot_price_coverage(prices: pd.DataFrame, output_path: Optional[str] = None):
    """Horizontal bars showing the observation window for each ticker."""
    fig, ax = plt.subplots(figsize=(12, max(3, len(prices.columns) * 0.6)))
    colors = plt.cm.tab10.colors  # type: ignore[attr-defined]
    for i, ticker in enumerate(prices.columns):
        px = prices[ticker].dropna()
        if px.empty:
            continue
        ax.barh(
            ticker, (px.index.max() - px.index.min()).days,
            left=px.index.min(), color=colors[i % len(colors)], alpha=0.8
        )
    ax.set_xlabel("Date")
    ax.set_title("Data coverage window per ticker", fontweight="bold")
    ax.invert_yaxis()
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return fig


# ---------------------------------------------------------------------------
# LaTeX table export
# ---------------------------------------------------------------------------

def data_quality_to_latex(stats: pd.DataFrame, output_path: Optional[str] = None) -> str:
    """Render the quality-stats DataFrame as a LaTeX longtable snippet."""
    display_cols = [
        "first_date", "last_date", "n_obs", "pct_missing",
        "n_gaps_gt2d", "n_zero_returns", "skewness", "excess_kurtosis",
        "annualised_vol_pct",
    ]
    col_labels = [
        "First obs.", "Last obs.", "N", r"\% miss.",
        "Gaps $>$2d", "Zero ret.", "Skew", "Ex.Kurt",
        r"Ann.Vol (\%)",
    ]
    df = stats[[c for c in display_cols if c in stats.columns]].copy()
    df.index.name = "Ticker"

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\caption{Data quality summary per ticker}",
        r"\label{tab:data_quality}",
        r"\begin{tabular}{l" + "r" * len(df.columns) + "}",
        r"\toprule",
        "Ticker & " + " & ".join(col_labels) + r" \\",
        r"\midrule",
    ]
    for ticker, row in df.iterrows():
        vals = []
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                vals.append("--")
            elif isinstance(v, float):
                vals.append(f"{v:.2f}")
            else:
                vals.append(str(v))
        lines.append(f"{ticker} & " + " & ".join(vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]

    latex = "\n".join(lines)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(latex)
    return latex


# ---------------------------------------------------------------------------
# Top-level convenience function
# ---------------------------------------------------------------------------

def run_data_quality_report(
    prices: pd.DataFrame,
    output_dir: Optional[str] = None,
    sigma_threshold: float = 5.0,
) -> Dict:
    """Run the full quality suite and optionally save artefacts.

    Returns a dict with keys:
        stats        : per-ticker quality DataFrame
        overlap      : pairwise coverage overlap DataFrame
        latex        : LaTeX table string
    """
    returns = np.log(prices / prices.shift(1))
    stats = ticker_quality_stats(prices, sigma_threshold=sigma_threshold)
    overlap = check_coverage_overlap(prices)
    latex = data_quality_to_latex(stats)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        stats.to_csv(os.path.join(output_dir, "data_quality_stats.csv"))
        overlap.to_csv(os.path.join(output_dir, "coverage_overlap.csv"))
        with open(os.path.join(output_dir, "data_quality_table.tex"), "w", encoding="utf-8") as fh:
            fh.write(latex)
        plot_missing_heatmap(prices, os.path.join(output_dir, "fig_missing_heatmap.png"))
        plot_return_outliers(returns, sigma_threshold, os.path.join(output_dir, "fig_return_outliers.png"))
        plot_price_coverage(prices, os.path.join(output_dir, "fig_price_coverage.png"))
        print(f"[data_quality] Artefacts saved to {output_dir}")

    return {"stats": stats, "overlap": overlap, "latex": latex}
