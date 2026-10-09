#!/usr/bin/env python3
"""Redraw the pipeline-generated dataset figures with print-legible type.

The figures produced inside pipeline.py were drawn at matplotlib's default
type sizes and then included in the thesis at roughly half their natural
width, which left the tick labels and legends too small to read on paper.
apply_figure_style() fixes the sizes for future runs; this script re-renders
the affected figures from the cached, frozen dataset so the current PDF can
be rebuilt without re-running the walk-forward.

No network access and no recomputation of results: prices and returns are
read from data/raw and data/processed exactly as the pipeline left them.

Usage
-----
    py -3 replot_figures.py
"""
from __future__ import annotations

import os

import pandas as pd

from thesis_app.pipeline import build_paths, describe_dataset, load_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    "dataset_prices.png",
    "dataset_volatility.png",
    "dataset_corr_heatmap.png",
    "dataset_return_dist.png",
]


def main() -> None:
    cfg = load_config(os.path.join(BASE_DIR, "config.yaml"))
    paths = build_paths(BASE_DIR)

    prices_path = os.path.join(paths.data_raw, "prices.csv")
    returns_path = os.path.join(paths.data_processed, "returns.csv")
    for path in (prices_path, returns_path):
        if not os.path.exists(path):
            raise SystemExit(f"Cached dataset missing: {path}. Run the full pipeline first.")

    prices = pd.read_csv(prices_path, index_col=0, parse_dates=True).sort_index()
    returns = pd.read_csv(returns_path, index_col=0, parse_dates=True).sort_index()

    before = {
        name: os.path.getsize(os.path.join(paths.figures, name))
        for name in TARGETS
        if os.path.exists(os.path.join(paths.figures, name))
    }

    print(f"prices  {prices.shape}  {prices.index.min().date()} .. {prices.index.max().date()}")
    print(f"returns {returns.shape}")
    describe_dataset(prices, returns, paths, cfg)

    print("\nredrawn:")
    for name in TARGETS:
        path = os.path.join(paths.figures, name)
        if not os.path.exists(path):
            print(f"  {name:<28} MISSING")
            continue
        old = before.get(name)
        size = os.path.getsize(path)
        delta = f"{old / 1024:.0f} -> {size / 1024:.0f} KB" if old else f"{size / 1024:.0f} KB"
        print(f"  {name:<28} {delta}")


if __name__ == "__main__":
    main()
