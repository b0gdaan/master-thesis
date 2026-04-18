"""
Helpers for thesis notebooks: plotting style, robust model selection, and concise interpretation text.
"""
from __future__ import annotations

from typing import Iterable, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def apply_thesis_plot_style() -> None:
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update(
        {
            "figure.figsize": (12, 6),
            "axes.titlesize": 16,
            "axes.labelsize": 12,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": True,
            "legend.framealpha": 0.9,
            "legend.facecolor": "white",
            "savefig.dpi": 140,
            "figure.dpi": 120,
        }
    )


def preferred_xgb_label(columns: Iterable[str]) -> Optional[str]:
    """Return the XGBoost column label present in *columns*, preferring GPU.

    Handles the GPU→CPU fallback rename: the walk-forward evaluator may
    produce 'XGB_GPU' (CUDA available) or 'XGB_CPU' (CPU fallback).
    """
    cols = list(columns)
    for name in ("XGB_GPU", "XGB_CPU"):
        if name in cols:
            return name
    return None


def best_ml_model_name(metrics: pd.DataFrame) -> Optional[str]:
    """Return the ML model (not Naive/AR1/DCC) with lowest RMSE."""
    if metrics.empty or "model" not in metrics.columns:
        return None
    excluded = {"Naive_Last", "AR1", "DCC_GARCH"}
    ml = metrics.loc[~metrics["model"].isin(excluded)].copy()
    if ml.empty:
        return None
    return str(ml.sort_values("RMSE").iloc[0]["model"])


def significance_stars(p_value: float) -> str:
    """Return conventional significance stars for a p-value."""
    if pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def interpretation_text(metric_name: str, higher_is_better: bool = True) -> str:
    direction = "higher" if higher_is_better else "lower"
    return (
        f"Interpretation: {direction} {metric_name} indicates stronger "
        "practical usefulness in the out-of-sample setting."
    )


def format_metrics_table(metrics: pd.DataFrame, highlight_best: bool = True) -> pd.DataFrame:
    """Return a display-ready copy of a metrics DataFrame.

    Rounds numeric columns, marks the best (lowest RMSE) row with '★',
    and adds a significance-star column for DM p-values when present.
    """
    out = metrics.copy()
    for col in ("MAE", "RMSE", "R2"):
        if col in out.columns:
            out[col] = out[col].apply(lambda v: f"{float(v):.4f}" if pd.notna(v) else "")
    if "p_value" in out.columns:
        out["sig"] = out["p_value"].apply(significance_stars)
    if highlight_best and "RMSE" in metrics.columns and not metrics.empty:
        best_idx = metrics["RMSE"].idxmin()
        out.loc[best_idx, "model"] = "★ " + str(out.loc[best_idx, "model"])
    return out


def summarise_signal_metrics(signal_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot signal metrics to a compact summary (one row per model).

    Keeps the most informative columns for quick notebook inspection.
    """
    keep = [c for c in ("signal_model", "BalancedAccuracy", "F1Down", "AUC",
                         "PrecisionDown", "RecallDown", "ExitRate",
                         "AvgReturnFlagged", "AvgReturnClear") if c in signal_df.columns]
    out = signal_df[keep].copy()
    for col in keep[1:]:
        out[col] = pd.to_numeric(out[col], errors="coerce").round(4)
    return out.reset_index(drop=True)


def print_experiment_summary(metrics: pd.DataFrame, dm: pd.DataFrame, label: str = "") -> None:
    """Print a concise experiment summary to stdout — useful at the top of notebooks."""
    sep = "─" * 60
    print(sep)
    if label:
        print(f"  {label}")
    print(sep)
    if not metrics.empty:
        best = metrics.sort_values("RMSE").iloc[0]
        print(f"  Best dependency model : {best['model']}  "
              f"RMSE={float(best['RMSE']):.4f}  R²={float(best['R2']):.3f}")
        xgb_col = preferred_xgb_label(metrics["model"].tolist())
        if xgb_col:
            row = metrics.loc[metrics["model"] == xgb_col]
            if not row.empty:
                r = row.iloc[0]
                print(f"  XGBoost               : RMSE={float(r['RMSE']):.4f}  R²={float(r['R2']):.3f}")
    if not dm.empty and "DM_stat" in dm.columns:
        for _, row in dm.iterrows():
            p = row.get("p_value", np.nan)
            stars = significance_stars(float(p)) if pd.notna(p) else ""
            print(f"  DM test vs {row.get('benchmark','?'):10s}: stat={row.get('DM_stat','?'):.2f}  "
                  f"p={p:.4f} {stars}")
    print(sep)
