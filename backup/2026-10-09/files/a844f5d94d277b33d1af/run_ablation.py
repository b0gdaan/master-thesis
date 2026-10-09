#!/usr/bin/env python3
"""Feature-group ablation for the dependency-forecasting layer.

Trains the same models on a nested sequence of feature sets, from a single
dependency lag up to the full matrix, so the marginal contribution of each
group can be read off directly. The walk-forward protocol, the split points
and the seeds are the ones the main pipeline uses; only the columns of X
change between runs.

Groups (each one contains all the previous ones):

    G1  dependency lag only            dep_lag1
    G2  + dependency history           further lags, momentum, z-score,
                                       multi-scale correlation structure
    G3  + Bitcoin returns              return lags, volatility, mean, squared
                                       return of the base asset
    G4  + related-asset returns        the same block for the paired asset
    G5  full model                     cross-asset interaction terms

Usage
-----
    py -3 run_ablation.py                  # representative pair, w = 30
    py -3 run_ablation.py --window 90
"""
from __future__ import annotations

import argparse
import os

import pandas as pd
import yaml

from thesis_app.pipeline import (
    build_features,
    build_target,
    fit_predict_walk_forward,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "outputs", "results")
TABLES_DIR = os.path.join(BASE_DIR, "outputs", "tables")

# Models carried into the thesis table: the linear leader and the two tree
# methods, which is where the interesting negative result sits.
REPORTED = ["Ridge", "RF", "XGB_GPU", "XGB_CPU"]

PRETTY = {
    "Ridge": "Ridge",
    "RF": "Random Forest",
    "XGB_GPU": "XGBoost",
    "XGB_CPU": "XGBoost",
}


def feature_groups(columns: list[str]) -> "dict[str, list[str]]":
    """Return the nested feature sets, as lists of column names."""
    dep_lag1 = ["dep_lag1"]

    dep_history = [c for c in columns if c.startswith("dep_")] + [
        c for c in columns if c.startswith("corr_")
    ]

    base_block = [
        c
        for c in columns
        if c.startswith("r_base_") or c in {"vol_base", "vol_base_60", "mean_base"}
    ]
    other_block = [
        c
        for c in columns
        if c.startswith("r_other_") or c in {"vol_other", "vol_other_60", "mean_other"}
    ]
    interaction = [c for c in columns if c in {"vol_ratio", "abs_spread", "abs_spread_20"}]

    g1 = dep_lag1
    g2 = sorted(set(g1) | set(dep_history))
    g3 = sorted(set(g2) | set(base_block))
    g4 = sorted(set(g3) | set(other_block))
    g5 = sorted(set(g4) | set(interaction))

    missing = sorted(set(columns) - set(g5))
    if missing:
        raise SystemExit(f"Feature groups do not cover every column; unassigned: {missing}")

    return {
        "G1 dependency lag only": g1,
        "G2 + dependency history": g2,
        "G3 + Bitcoin returns": g3,
        "G4 + related-asset returns": g4,
        "G5 full model": g5,
    }


def latex_table(df: pd.DataFrame, label_models: list[str]) -> str:
    """Render the ablation result as the LaTeX table the thesis inputs."""
    header = " & ".join(f"\\multicolumn{{2}}{{c}}{{{m}}}" for m in label_models)
    sub = " & ".join(["RMSE & $R^2$"] * len(label_models))
    lines = [
        "\\begin{tabular}{lr" + "rr" * len(label_models) + "}",
        "    \\toprule",
        f"    Feature set & \\# & {header} \\\\",
        "    \\cmidrule(lr){3-" + str(2 + 2 * len(label_models)) + "}",
        f"     &  & {sub} \\\\",
        "    \\midrule",
    ]
    for _, row in df.iterrows():
        cells = [row["group"].replace("+", "$+$"), str(int(row["n_features"]))]
        for m in label_models:
            cells.append(f"{row[f'{m}_RMSE']:.4f}")
            cells.append(f"{row[f'{m}_R2']:.4f}")
        lines.append("    " + " & ".join(cells) + " \\\\")
    lines += ["    \\bottomrule", "\\end{tabular}"]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="BTC-USD")
    ap.add_argument("--other", default="^GSPC")
    ap.add_argument("--window", type=int, default=30)
    args = ap.parse_args()

    with open(os.path.join(BASE_DIR, "config.yaml"), encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    returns = pd.read_csv(
        os.path.join(BASE_DIR, "data", "processed", "returns.csv"),
        index_col=0,
        parse_dates=True,
    )

    use_fisher = bool(cfg.get("use_fisher_transform", True))
    horizon = int(cfg.get("forecast_horizon", 1))

    y = build_target(returns, args.base, args.other, args.window, horizon, use_fisher)
    X_full = build_features(returns, args.window, y, args.base, args.other, horizon)
    y_aligned = y.loc[X_full.index]

    groups = feature_groups(list(X_full.columns))

    print(f"Ablation: {args.base} vs {args.other}, w={args.window}, "
          f"{len(X_full)} aligned observations, {X_full.shape[1]} features total")

    rows = []
    for name, cols in groups.items():
        print(f"  [{name}]  {len(cols)} features ... ", end="", flush=True)
        _, metrics = fit_predict_walk_forward(
            X=X_full[cols],
            y=y_aligned,
            min_train=int(cfg["min_train_size"]),
            refit_every=int(cfg["refit_every"]),
            random_state=int(cfg["random_state"]),
            use_xgb=True,
            xgb_device=str(cfg.get("xgb_device", "cuda")),
        )
        row = {"group": name, "n_features": len(cols)}
        for _, m in metrics.iterrows():
            if m["model"] in REPORTED:
                key = "XGB_GPU" if m["model"].startswith("XGB") else m["model"]
                row[f"{key}_RMSE"] = m["RMSE"]
                row[f"{key}_R2"] = m["R2"]
                row[f"{key}_MAE"] = m["MAE"]
        rows.append(row)
        print("done")

    df = pd.DataFrame(rows)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)
    csv_path = os.path.join(RESULTS_DIR, "feature_ablation.csv")
    df.to_csv(csv_path, index=False)

    label_models = ["Ridge", "RF", "XGB_GPU"]
    tex = latex_table(df, label_models)
    tex = tex.replace("{RF}", "{Random Forest}").replace("{XGB_GPU}", "{XGBoost}")
    tex_path = os.path.join(TABLES_DIR, "feature_ablation_table.tex")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write(tex + "\n")

    print(f"\nwrote {csv_path}")
    print(f"wrote {tex_path}\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
