"""
Historical regime analysis for crypto vs. traditional asset correlations.

Defines major market regimes since 2017 and computes per-regime rolling
correlation statistics for any base/other pair.  Results are exportable as
LaTeX tables and publication-quality annotated figures.

Regime catalogue
----------------
Each entry in REGIMES is:
    label -> (start_date, end_date, hex_colour, short_description)

Usage
-----
    from thesis_app.regime_analysis import compute_regime_stats, plot_rolling_corr_with_regimes
    import pandas as pd, numpy as np

    prices  = pd.read_csv("data/raw/prices.csv", index_col=0, parse_dates=True)
    returns = np.log(prices / prices.shift(1))
    corr    = returns["BTC-USD"].rolling(30).corr(returns["^GSPC"])

    stats = compute_regime_stats(corr, returns["BTC-USD"])
    fig   = plot_rolling_corr_with_regimes(corr, pair_label="BTC-USD / S&P 500",
                                           window=30, output_path="fig_regimes.png")
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd


# Format: "label": (start, end, colour, description)
REGIMES: Dict[str, Tuple[str, str, str, str]] = {
    "Crypto Bull\n2017":        ("2017-01-01", "2017-12-17", "#2ca02c", "Initial crypto bull run"),
    "Crypto Bear\n2018":        ("2018-01-01", "2018-12-31", "#d62728", "Post-ATH bear market"),
    "Calm\n2019":               ("2019-01-01", "2019-12-31", "#aec7e8", "Low-volatility recovery"),
    "COVID Crash":              ("2020-02-20", "2020-03-23", "#8c564b", "Global pandemic shock"),
    "COVID\nRecovery":          ("2020-03-24", "2020-12-31", "#17becf", "Central bank liquidity surge"),
    "Crypto Bull\n2021":        ("2021-01-01", "2021-11-10", "#2ca02c", "All-time highs, institutional entry"),
    "Rate Hike\nCycle":         ("2022-01-01", "2022-06-15", "#ff7f0e", "Fed tightening, risk-off"),
    "Terra/Luna\nCollapse":     ("2022-05-01", "2022-06-30", "#9467bd", "Algorithmic stablecoin failure"),
    "FTX\nCollapse":            ("2022-11-01", "2022-11-30", "#e377c2", "Centralised exchange failure"),
    "Crypto\nRecovery 2023":    ("2023-01-01", "2023-12-31", "#bcbd22", "Gradual market normalisation"),
    "BTC ETF /\nHalving 2024":  ("2024-01-01", "2024-06-30", "#1f77b4", "Spot ETF approval + halving"),
}

# Macro indicator regimes (for VIX / rates context)
MACRO_REGIMES: Dict[str, Tuple[str, str, str, str]] = {
    "Low VIX\n(<15)":       ("2019-01-01", "2020-02-19", "#aec7e8", "Pre-COVID calm"),
    "High VIX\n(>30)":      ("2020-02-20", "2020-05-31", "#d62728", "Pandemic fear spike"),
    "Hike\nCycle":          ("2022-03-16", "2023-07-26", "#ff7f0e", "Fed funds 0→5.25 %"),
}


def compute_regime_stats(
    rolling_corr: pd.Series,
    base_returns: Optional[pd.Series] = None,
    regimes: Optional[Dict] = None,
) -> pd.DataFrame:
    """For each regime, compute correlation and (optionally) volatility statistics.

    Parameters
    ----------
    rolling_corr : pd.Series
        Time series of rolling Pearson correlations.
    base_returns : pd.Series, optional
        Log-returns of the base asset (e.g. BTC-USD).  If provided, annualised
        volatility is added to the table.
    regimes : dict, optional
        Override REGIMES.  Defaults to module-level REGIMES.

    Returns
    -------
    pd.DataFrame  with columns:
        regime, start, end, n_obs, mean_corr, median_corr, std_corr,
        min_corr, max_corr, [ann_vol_pct if base_returns provided]
    """
    if regimes is None:
        regimes = REGIMES

    rows = []
    for label, (start, end, _colour, description) in regimes.items():
        mask = (rolling_corr.index >= pd.Timestamp(start)) & (rolling_corr.index <= pd.Timestamp(end))
        segment = rolling_corr.loc[mask].dropna()
        if segment.empty:
            continue
        row: dict = {
            "regime": label.replace("\n", " "),
            "description": description,
            "start": start,
            "end": end,
            "n_obs": len(segment),
            "mean_corr": round(float(segment.mean()), 3),
            "median_corr": round(float(segment.median()), 3),
            "std_corr": round(float(segment.std()), 3),
            "min_corr": round(float(segment.min()), 3),
            "max_corr": round(float(segment.max()), 3),
        }
        if base_returns is not None:
            ret_mask = (base_returns.index >= pd.Timestamp(start)) & (base_returns.index <= pd.Timestamp(end))
            ret_seg = base_returns.loc[ret_mask].dropna()
            row["ann_vol_pct"] = (
                round(float(ret_seg.std() * np.sqrt(252) * 100), 1) if len(ret_seg) > 1 else np.nan
            )
        rows.append(row)

    return pd.DataFrame(rows)


def compute_regime_corr_matrix(
    returns: pd.DataFrame,
    regime_label: str,
    regimes: Optional[Dict] = None,
) -> Optional[pd.DataFrame]:
    """Full Pearson correlation matrix for all tickers during a named regime."""
    if regimes is None:
        regimes = REGIMES
    if regime_label not in regimes:
        return None
    start, end, _, _ = regimes[regime_label]
    mask = (returns.index >= pd.Timestamp(start)) & (returns.index <= pd.Timestamp(end))
    segment = returns.loc[mask].dropna(how="all")
    return segment.corr() if len(segment) > 5 else None


def plot_rolling_corr_with_regimes(
    rolling_corr: pd.Series,
    pair_label: str = "BTC-USD / Asset",
    window: int = 30,
    regimes: Optional[Dict] = None,
    output_path: Optional[str] = None,
    alpha_shade: float = 0.18,
) -> plt.Figure:
    """Plot rolling correlation time series with shaded regime bands.

    Parameters
    ----------
    rolling_corr : pd.Series  — rolling Pearson correlation series
    pair_label   : str         — used in title and y-label
    window       : int         — the rolling window size (for subtitle)
    regimes      : dict        — override REGIMES
    output_path  : str         — if given, saves figure to this path
    alpha_shade  : float       — transparency of regime bands
    """
    if regimes is None:
        regimes = REGIMES

    fig, ax = plt.subplots(figsize=(16, 5))

    legend_patches = []
    seen_colours: Dict[str, bool] = {}
    for label, (start, end, colour, description) in regimes.items():
        ts, te = pd.Timestamp(start), pd.Timestamp(end)
        ax.axvspan(ts, te, color=colour, alpha=alpha_shade, linewidth=0)
        clean_label = label.replace("\n", " ")
        if colour not in seen_colours:
            legend_patches.append(mpatches.Patch(color=colour, alpha=0.5, label=clean_label))
            seen_colours[colour] = True
        else:
            # Disambiguate same colour (Terra/Luna overlaps Rate Hike)
            legend_patches.append(mpatches.Patch(color=colour, alpha=0.5, label=clean_label))

    ax.plot(rolling_corr.index, rolling_corr.values, color="steelblue", linewidth=1.2, label=f"{window}d corr")
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")

    smooth = rolling_corr.rolling(90, min_periods=30).mean()
    ax.plot(smooth.index, smooth.values, color="darkorange", linewidth=1.8,
            linestyle="-", alpha=0.85, label="90d MA")

    ax.set_ylabel(f"Rolling {window}d Pearson ρ", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_title(f"Rolling correlation: {pair_label} — with historical market regimes",
                 fontsize=13, fontweight="bold")
    ax.set_ylim(-1.05, 1.05)

    line_legend = ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    ax.add_artist(line_legend)
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=min(6, len(legend_patches)),
        fontsize=7.5,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.05),
    )

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    if output_path:
        fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return fig


def plot_regime_corr_boxplot(
    returns: pd.DataFrame,
    base: str,
    other: str,
    window: int = 30,
    regimes: Optional[Dict] = None,
    output_path: Optional[str] = None,
) -> plt.Figure:
    """Box-plot of rolling correlations grouped by regime."""
    if regimes is None:
        regimes = REGIMES

    rolling_corr = returns[base].rolling(window).corr(returns[other])

    data, labels, colours = [], [], []
    for label, (start, end, colour, _) in regimes.items():
        mask = (rolling_corr.index >= pd.Timestamp(start)) & (rolling_corr.index <= pd.Timestamp(end))
        seg = rolling_corr.loc[mask].dropna()
        if len(seg) < 5:
            continue
        data.append(seg.values)
        labels.append(label.replace("\n", " "))
        colours.append(colour)

    fig, ax = plt.subplots(figsize=(max(10, len(data) * 1.5), 5))
    bp = ax.boxplot(data, patch_artist=True, notch=False, vert=True,
                    medianprops=dict(color="black", linewidth=2))
    for patch, colour in zip(bp["boxes"], colours):
        patch.set_facecolor(colour)
        patch.set_alpha(0.7)

    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
    ax.set_ylabel(f"Rolling {window}d Pearson ρ", fontsize=11)
    ax.set_title(f"Correlation distribution by regime: {base} / {other}", fontsize=13, fontweight="bold")
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return fig


def plot_all_pairs_regime_heatmap(
    returns: pd.DataFrame,
    pairs: List[Tuple[str, str]],
    regimes: Optional[Dict] = None,
    output_path: Optional[str] = None,
) -> plt.Figure:
    """Heatmap: rows = pairs, columns = regimes, cells = mean correlation."""
    if regimes is None:
        regimes = REGIMES

    regime_labels = [label.replace("\n", " ") for label in regimes]
    pair_labels   = [f"{a}/{b}" for a, b in pairs]
    mat = np.full((len(pairs), len(regime_labels)), np.nan)

    for pi, (a, b) in enumerate(pairs):
        if a not in returns.columns or b not in returns.columns:
            continue
        corr_series = returns[a].rolling(30).corr(returns[b])
        for ri, (label, (start, end, _, _)) in enumerate(regimes.items()):
            mask = (corr_series.index >= pd.Timestamp(start)) & (corr_series.index <= pd.Timestamp(end))
            seg = corr_series.loc[mask].dropna()
            if len(seg) >= 5:
                mat[pi, ri] = seg.mean()

    fig, ax = plt.subplots(figsize=(max(12, len(regime_labels) * 1.5), max(4, len(pairs) * 0.8)))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(regime_labels)))
    ax.set_xticklabels(regime_labels, rotation=40, ha="right", fontsize=9)
    ax.set_yticks(range(len(pair_labels)))
    ax.set_yticklabels(pair_labels, fontsize=10)

    for pi in range(len(pairs)):
        for ri in range(len(regime_labels)):
            val = mat[pi, ri]
            if not np.isnan(val):
                ax.text(ri, pi, f"{val:.2f}", ha="center", va="center",
                        fontsize=8, color="black" if abs(val) < 0.6 else "white")

    plt.colorbar(im, ax=ax, label="Mean 30d Pearson ρ")
    ax.set_title("Mean rolling correlation by pair and market regime", fontsize=13, fontweight="bold")
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return fig


def regime_stats_to_latex(
    stats: pd.DataFrame,
    pair_label: str = "BTC-USD / Asset",
    window: int = 30,
    output_path: Optional[str] = None,
) -> str:
    """Format regime statistics as a LaTeX table."""
    display_cols = ["regime", "start", "end", "n_obs", "mean_corr",
                    "std_corr", "min_corr", "max_corr"]
    if "ann_vol_pct" in stats.columns:
        display_cols.append("ann_vol_pct")

    col_labels_map = {
        "regime": "Regime", "start": "Start", "end": "End",
        "n_obs": "$N$", "mean_corr": r"$\bar{\rho}$",
        "std_corr": r"$\sigma_\rho$", "min_corr": "Min $\rho$",
        "max_corr": "Max $\rho$", "ann_vol_pct": r"Ann.Vol (\%)",
    }
    df = stats[[c for c in display_cols if c in stats.columns]].copy()
    col_headers = [col_labels_map.get(c, c) for c in df.columns]

    ncols = len(df.columns)
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        rf"\caption{{Rolling {window}-day Pearson correlation by historical regime: {pair_label}}}",
        r"\label{tab:regime_corr_" + pair_label.replace("/", "").replace(" ", "").replace("-", "").replace("^", "") + "}",
        r"\begin{tabular}{l" + "r" * (ncols - 1) + "}",
        r"\toprule",
        " & ".join(col_headers) + r" \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        vals = []
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                vals.append("--")
            elif col in ("mean_corr", "std_corr", "min_corr", "max_corr"):
                vals.append(f"{float(v):.3f}")
            elif col == "ann_vol_pct":
                vals.append(f"{float(v):.1f}")
            else:
                vals.append(str(v))
        lines.append(" & ".join(vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]

    latex = "\n".join(lines)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(latex)
    return latex


def run_regime_analysis(
    prices: pd.DataFrame,
    base: str,
    others: List[str],
    windows: List[int],
    output_dir: Optional[str] = None,
    regimes: Optional[Dict] = None,
) -> Dict:
    """Run full regime analysis for all base/other pairs and windows.

    Parameters
    ----------
    prices     : DataFrame of adjusted close prices (index = dates)
    base       : ticker of the base asset (e.g. "BTC-USD")
    others     : list of comparison tickers
    windows    : rolling window sizes (days)
    output_dir : if given, saves all figures and tables here
    regimes    : override REGIMES

    Returns
    -------
    dict keyed by (other, window) -> {"stats": DataFrame, "latex": str}
    """
    if regimes is None:
        regimes = REGIMES

    returns = np.log(prices / prices.shift(1))
    results: Dict = {}

    all_pairs = [(base, o) for o in others if o in returns.columns]

    for other in others:
        if other not in returns.columns:
            print(f"[regime_analysis] Skipping {other}: not in returns DataFrame")
            continue
        for window in windows:
            corr = returns[base].rolling(window).corr(returns[other]).dropna()
            stats = compute_regime_stats(corr, returns[base], regimes=regimes)
            latex = regime_stats_to_latex(
                stats,
                pair_label=f"{base} / {other}",
                window=window,
            )
            results[(other, window)] = {"stats": stats, "latex": latex}

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                safe = f"{base.replace('-','').replace('^','')}_{other.replace('-','').replace('^','')}_{window}d"
                stats.to_csv(os.path.join(output_dir, f"regime_stats_{safe}.csv"), index=False)
                with open(os.path.join(output_dir, f"regime_table_{safe}.tex"), "w", encoding="utf-8") as fh:
                    fh.write(latex)
                plot_rolling_corr_with_regimes(
                    corr,
                    pair_label=f"{base} / {other}",
                    window=window,
                    regimes=regimes,
                    output_path=os.path.join(output_dir, f"fig_regime_corr_{safe}.png"),
                )
                plot_regime_corr_boxplot(
                    returns, base, other, window=window, regimes=regimes,
                    output_path=os.path.join(output_dir, f"fig_regime_boxplot_{safe}.png"),
                )
                print(f"[regime_analysis] Saved artefacts for {base}/{other} w={window}")

    # Cross-pair heatmap for the most common window
    if output_dir and all_pairs:
        primary_window = windows[1] if len(windows) > 1 else windows[0]  # prefer 30d
        plot_all_pairs_regime_heatmap(
            returns, all_pairs, regimes=regimes,
            output_path=os.path.join(output_dir, "fig_regime_heatmap_all_pairs.png"),
        )

    return results
