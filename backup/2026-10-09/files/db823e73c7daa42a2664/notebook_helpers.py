"""
Helpers for thesis notebooks: plotting style, robust model selection, and concise interpretation text.
"""
from __future__ import annotations

import math

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


def preferred_xgb_label(columns) -> str | None:
    for name in ["XGB_GPU", "XGB_CPU"]:
        if name in columns:
            return name
    return None


def best_ml_model_name(metrics: pd.DataFrame) -> str | None:
    if metrics.empty or "model" not in metrics.columns:
        return None
    excluded = {"Naive_Last", "AR1", "DCC_GARCH"}
    ml = metrics.loc[~metrics["model"].isin(excluded)].copy()
    if ml.empty:
        return None
    return ml.sort_values("RMSE").iloc[0]["model"]


def significance_stars(p_value: float) -> str:
    """Return LaTeX significance stars for a p-value.
    Returns an empty string for NaN, inf, or negative inputs."""
    try:
        p = float(p_value)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(p) or p < 0:
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def interpretation_text(metric_name: str, higher_is_better: bool = True) -> str:
    direction = "higher" if higher_is_better else "lower"
    return f"Interpretation: {direction} {metric_name} indicates stronger practical usefulness in the out-of-sample setting."
