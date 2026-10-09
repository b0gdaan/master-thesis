import os
import sys
import json

import matplotlib
matplotlib.use("Agg")
import yaml
import math
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
matplotlib.use("Agg")

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from sklearn.linear_model import Ridge, LinearRegression, ElasticNet
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from scipy import stats

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False

# Econometric benchmark (DCC-GARCH) implemented via "arch" if available
try:
    from .dcc import dcc_garch_fit_predict
    DCC_AVAILABLE = True
except Exception:
    DCC_AVAILABLE = False


@dataclass
class Paths:
    base_dir: str
    data_raw: str
    data_processed: str
    outputs: str
    figures: str
    results: str
    predictions: str
    tables: str
    models: str


def _ensure_dirs(paths: Paths) -> None:
    for d in [paths.data_raw, paths.data_processed, paths.figures, paths.results, paths.predictions, paths.tables, paths.models]:
        os.makedirs(d, exist_ok=True)


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_paths(base_dir: str) -> Paths:
    return Paths(
        base_dir=base_dir,
        data_raw=os.path.join(base_dir, "data", "raw"),
        data_processed=os.path.join(base_dir, "data", "processed"),
        outputs=os.path.join(base_dir, "outputs"),
        figures=os.path.join(base_dir, "outputs", "figures"),
        results=os.path.join(base_dir, "outputs", "results"),
        predictions=os.path.join(base_dir, "outputs", "predictions"),
        tables=os.path.join(base_dir, "outputs", "tables"),
        models=os.path.join(base_dir, "models"),
    )


def _pick_price_panel(download_df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance output can be MultiIndex with fields like Close/Open/High/Low/Volume.
    We use adjusted prices via auto_adjust=True and then take 'Close'.
    Still supports legacy 'Adj Close' if present.
    """
    if isinstance(download_df.columns, pd.MultiIndex):
        level0 = download_df.columns.get_level_values(0)
        if "Adj Close" in level0:
            return download_df["Adj Close"]
        if "Close" in level0:
            return download_df["Close"]
        raise KeyError(f"Neither 'Adj Close' nor 'Close' found. Level0={sorted(set(level0))}")
    else:
        if "Adj Close" in download_df.columns:
            return download_df["Adj Close"]
        if "Close" in download_df.columns:
            return download_df["Close"]
        raise KeyError(f"Neither 'Adj Close' nor 'Close' found. Columns={list(download_df.columns)}")


def fetch_prices_csv(paths: Paths, tickers: List[str], start: str, end: Optional[str]) -> pd.DataFrame:
    """
    Cache strategy:
    - If prices.csv exists: load it.
    - Else: download and save to CSV.
    """
    prices_path = os.path.join(paths.data_raw, "prices.csv")
    if os.path.exists(prices_path):
        df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
        missing = [t for t in tickers if t not in df.columns]
        if not missing:
            return df

    dl = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        group_by="column",
        progress=True,
        threads=True
    )
    prices = _pick_price_panel(dl).dropna()
    prices.to_csv(prices_path, encoding="utf-8")
    return prices


def compute_returns_csv(paths: Paths, prices: pd.DataFrame) -> pd.DataFrame:
    returns_path = os.path.join(paths.data_processed, "returns.csv")
    if os.path.exists(returns_path):
        return pd.read_csv(returns_path, index_col=0, parse_dates=True)
    rets = np.log(prices / prices.shift(1)).dropna()
    rets.to_csv(returns_path, encoding="utf-8")
    return rets


def fisher_z(r: pd.Series, eps: float = 1e-6) -> pd.Series:
    """Fisher z-transform: z = arctanh(r). Clip to (-1,1) to avoid inf."""
    r2 = r.clip(-1 + eps, 1 - eps)
    return np.arctanh(r2)


def inv_fisher_z(z: pd.Series) -> pd.Series:
    """Inverse Fisher transform: r = tanh(z)."""
    return np.tanh(z)


def rolling_corr(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    return a.rolling(window).corr(b)


def build_dependency_target(
    returns: pd.DataFrame,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool
) -> pd.Series:
    """
    Target is future rolling correlation (t+h) for the pair (base, other).
    If use_fisher=True, return z_t = arctanh(rho_t) in the target space.
    """
    corr = rolling_corr(returns[base], returns[other], window).dropna()
    y = corr.shift(-horizon).dropna()
    if use_fisher:
        y = fisher_z(y)
    return y


def build_features(
    returns: pd.DataFrame,
    window: int,
    y_target: pd.Series,
    base: str,
    other: str,
    horizon: int
) -> pd.DataFrame:
    """
    Feature set (information at time t) to forecast y(t+h):
    - lags of the current dependency proxy (y shifted back by h)
    - rolling volatility of base/other returns
    - lagged returns (1,2,5 days) for both assets
    - rolling mean returns (trend) for both assets
    """
    idx = y_target.index
    X = pd.DataFrame(index=idx)

    # reconstruct approximate "current" dependency in the same space as y (z-space if fisher was used)
    # y_target is y(t+h). For h=1, y_target.shift(+1) approximates y(t).
    y_current = y_target.shift(+horizon).reindex(idx)

    # dependency lags
    X["dep_lag1"] = y_current.shift(1)
    X["dep_lag2"] = y_current.shift(2)
    X["dep_lag5"] = y_current.shift(5)

    # volatilities (returns space)
    X["vol_base"] = returns[base].rolling(window).std().reindex(idx)
    X["vol_other"] = returns[other].rolling(window).std().reindex(idx)

    # lagged returns
    for lag in [1, 2, 5]:
        X[f"r_base_lag{lag}"] = returns[base].shift(lag).reindex(idx)
        X[f"r_other_lag{lag}"] = returns[other].shift(lag).reindex(idx)

    # rolling means (trend proxies)
    X["mean_base"] = returns[base].rolling(window).mean().reindex(idx)
    X["mean_other"] = returns[other].rolling(window).mean().reindex(idx)

    X = X.dropna()
    return X


def walk_forward_splits(n: int, min_train: int) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Expanding window, 1-step ahead."""
    splits = []
    for t in range(min_train, n):
        splits.append((np.arange(0, t), np.array([t])))
    return splits


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def diebold_mariano(
    e_model: np.ndarray,
    e_bench: np.ndarray,
    h: int = 1,
    power: int = 2,
    nw_lag: Optional[int] = None
) -> Dict[str, float]:
    """
    Diebold–Mariano test for equal predictive accuracy.
    Loss differential d_t = |e_bench|^p - |e_model|^p (positive => model better).
    For h=1, serial correlation is often small; we still allow Newey–West with lag.
    """
    e_model = np.asarray(e_model, dtype=float)
    e_bench = np.asarray(e_bench, dtype=float)
    mask = ~np.isnan(e_model) & ~np.isnan(e_bench)
    e_model = e_model[mask]
    e_bench = e_bench[mask]
    T = len(e_model)
    if T < 30:
        return {"DM_stat": np.nan, "p_value": np.nan, "n": float(T)}

    d = (np.abs(e_bench) ** power) - (np.abs(e_model) ** power)

    # Newey–West variance estimate
    if nw_lag is None:
        nw_lag = max(0, h - 1)

    d_mean = d.mean()
    gamma0 = np.var(d, ddof=1)

    var = gamma0
    for lag in range(1, nw_lag + 1):
        cov = np.cov(d[lag:], d[:-lag], ddof=1)[0, 1]
        w = 1.0 - lag / (nw_lag + 1.0)
        var += 2 * w * cov

    dm = d_mean / np.sqrt(var / T) if var > 0 else np.nan

    # asymptotically ~ N(0,1); small sample: use t with T-1
    p = 2 * (1 - stats.t.cdf(np.abs(dm), df=T - 1)) if np.isfinite(dm) else np.nan
    return {"DM_stat": float(dm), "p_value": float(p), "n": float(T)}


def fit_predict_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int,
    refit_every: int,
    random_state: int,
    use_xgb: bool
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fit multiple models in walk-forward manner with periodic refit.
    Returns:
      - pred_df: columns are model names, index = y index
      - metrics_df: MAE/RMSE/R2 per model
    """
    Xv = X.values
    yv = y.loc[X.index].values
    idx = X.index

    splits = walk_forward_splits(len(idx), min_train)

    model_specs = {
        "Naive_Last": None,  # predict y(t+h) ~= y(t) (persistence in target space)
        "AR1": LinearRegression(),
        "ElasticNet": ElasticNet(random_state=random_state, max_iter=5000),
        "Ridge": Ridge(),
        "RF": RandomForestRegressor(n_estimators=400, random_state=random_state, n_jobs=-1),
    }

    if use_xgb and XGB_AVAILABLE:
        try:
            model_specs["XGB_GPU"] = xgb.XGBRegressor(
                n_estimators=1000,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                tree_method="gpu_hist",
                predictor="gpu_predictor",
                random_state=random_state,
            )
        except Exception:
            model_specs["XGB_CPU"] = xgb.XGBRegressor(
                n_estimators=1000,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=random_state,
            )

    preds = {name: np.full(len(idx), np.nan, dtype=float) for name in model_specs.keys()}

    # persistence baseline uses last observed y (in the target space)
    y_series = pd.Series(yv, index=idx)

    fitted = {}
    last_refit_at = -10**9

    for (tr, te) in splits:
        t = int(te[0])

        if (t - last_refit_at) >= refit_every:
            last_refit_at = t
            X_tr, y_tr = Xv[tr], yv[tr]

            # AR(1): y_{t} = a + b*y_{t-1}
            arX = np.vstack([y_series.iloc[tr].shift(1).values]).T
            mask = ~np.isnan(arX[:, 0])
            if mask.sum() > 10:
                model_specs["AR1"].fit(arX[mask], y_tr[mask])

            for name, m in model_specs.items():
                if m is None or name == "AR1":
                    continue
                try:
                    m.fit(X_tr, y_tr)
                    fitted[name] = m
                except Exception:
                    pass

        # predict
        if not np.isnan(y_series.iloc[t-1]):
            preds["Naive_Last"][t] = y_series.iloc[t-1]

        ar_feat = np.array([[y_series.iloc[t-1]]], dtype=float)
        if not np.isnan(ar_feat).any():
            try:
                preds["AR1"][t] = model_specs["AR1"].predict(ar_feat)[0]
            except Exception:
                pass

        for name in ["ElasticNet", "Ridge", "RF", "XGB_GPU", "XGB_CPU"]:
            if name in fitted:
                try:
                    preds[name][t] = fitted[name].predict(Xv[t:t+1])[0]
                except Exception:
                    pass

    pred_df = pd.DataFrame(preds, index=idx)

    metrics = []
    for name in pred_df.columns:
        mask = ~pred_df[name].isna()
        if mask.sum() < 50:
            continue
        yt = y.loc[pred_df.index][mask].values
        yp = pred_df.loc[mask, name].values
        metrics.append({
            "model": name,
            "MAE": float(mean_absolute_error(yt, yp)),
            "RMSE": _rmse(yt, yp),
            "R2": float(r2_score(yt, yp)),
            "n_test": int(mask.sum()),
        })
    metrics_df = pd.DataFrame(metrics).sort_values("RMSE")
    return pred_df, metrics_df


def save_plot_series(out_path: str, title: str, series_dict: Dict[str, pd.Series], figsize=(12, 5)) -> None:
    plt.figure(figsize=figsize)
    for label, s in series_dict.items():
        plt.plot(s.index, s.values, label=label)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_plot_actual_vs_preds(y: pd.Series, pred_df: pd.DataFrame, out_path: str, title: str, top_k: int = 3) -> None:
    plt.figure(figsize=(12, 5))
    plt.plot(y.index, y.values, label="Actual", linewidth=1.8)

    cols = [c for c in pred_df.columns if pred_df[c].notna().sum() > 50]
    # plot top_k models by RMSE if possible
    for c in cols[:top_k]:
        plt.plot(pred_df.index, pred_df[c].values, label=c, alpha=0.9)

    plt.legend()
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def describe_dataset(prices: pd.DataFrame, returns: pd.DataFrame, paths: Paths) -> None:
    """
    Create minimal, defense-friendly dataset diagnostics:
      - price trajectories
      - return volatility over time
      - correlation heatmap (returns)
    """
    # Prices
    plt.figure(figsize=(12, 6))
    for c in prices.columns:
        plt.plot(prices.index, prices[c], label=c, linewidth=1)
    plt.title("Adjusted prices (Yahoo Finance)")
    plt.legend(loc="best", ncol=2, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_prices.png"))
    plt.close()

    # Rolling volatility
    plt.figure(figsize=(12, 5))
    roll = returns.rolling(30).std()
    for c in roll.columns:
        plt.plot(roll.index, roll[c], label=c, linewidth=1)
    plt.title("Rolling 30-day volatility of log-returns")
    plt.legend(loc="best", ncol=2, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_volatility.png"))
    plt.close()

    # Correlation heatmap (as simple image, no seaborn)
    corr = returns.corr()
    plt.figure(figsize=(8, 6))
    plt.imshow(corr.values, aspect="auto")
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    plt.yticks(range(len(corr.index)), corr.index)
    plt.title("Correlation matrix (log-returns)")
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_corr_heatmap.png"))
    plt.close()

    # Basic tables
    summary = {
        "n_days_prices": int(len(prices)),
        "n_days_returns": int(len(returns)),
        "start": str(prices.index.min().date()) if len(prices) else None,
        "end": str(prices.index.max().date()) if len(prices) else None,
        "tickers": list(prices.columns),
    }
    with open(os.path.join(paths.results, "dataset_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def write_run_metadata(paths: Paths, cfg: Dict) -> None:
    """Save reproducibility metadata: versions and access date."""
    meta = {
        "python": sys.version,
        "yahoo_access_date": cfg.get("yahoo_access_date", None),
        "config": cfg,
    }
    try:
        import importlib.metadata as md
        packages = ["numpy", "pandas", "scikit-learn", "scipy", "yfinance", "xgboost", "torch", "pyarrow", "arch"]
        vers = {}
        for p in packages:
            try:
                vers[p] = md.version(p)
            except Exception:
                pass
        meta["package_versions"] = vers
    except Exception:
        pass

    with open(os.path.join(paths.results, "run_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def metrics_to_latex(metrics_df: pd.DataFrame, out_tex: str, caption: str = "Out-of-sample forecasting metrics", label: str = "tab:metrics") -> None:
    """Create a LaTeX table snippet for direct inclusion."""
    if metrics_df.empty:
        return
    cols = ["dependency", "window", "target_space", "model", "MAE", "RMSE", "R2", "n_test"]
    df = metrics_df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    # format floats
    for c in ["MAE", "RMSE", "R2"]:
        df[c] = df[c].astype(float).map(lambda x: f"{x:.4f}")
    df["n_test"] = df["n_test"].astype(int).astype(str)

    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\caption{" + caption + r"}")
    lines.append(r"\label{" + label + r"}")
    lines.append(r"\begin{tabular}{lllp{2.8cm}rrrr}")
    lines.append(r"\toprule")
    lines.append(r"Dependency & $w$ & Space & Model & MAE & RMSE & $R^2$ & $n$ \\")
    lines.append(r"\midrule")
    for _, row in df.iterrows():
        lines.append(
            f"{row['dependency']} & {row['window']} & {row['target_space']} & {row['model']} & {row['MAE']} & {row['RMSE']} & {row['R2']} & {row['n_test']} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_single_experiment(
    returns: pd.DataFrame,
    paths: Paths,
    cfg: Dict,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Run ML forecasts for one pair (base, other) and one rolling window.
    Also compute DCC benchmark if available.
    Returns: pred_output_df, metrics_df (best-per-model), dm_df
    """
    target_space = "fisher_z" if use_fisher else "raw_corr"

    y = build_dependency_target(
        returns=returns,
        base=base,
        other=other,
        window=window,
        horizon=horizon,
        use_fisher=use_fisher
    )

    X = build_features(
        returns=returns,
        window=window,
        y_target=y,
        base=base,
        other=other,
        horizon=horizon
    )

    y_aligned = y.loc[X.index]
    pred_df, metrics_df = fit_predict_walk_forward(
        X=X,
        y=y_aligned,
        min_train=int(cfg["min_train_size"]),
        refit_every=int(cfg["refit_every"]),
        random_state=int(cfg["random_state"]),
        use_xgb=bool(cfg.get("use_xgboost", True))
    )

    dep_name = f"corr_{base}_{other}"
    pred_out = os.path.join(paths.predictions, f"{dep_name}_w{window}_{target_space}_predictions.csv")

    out_df = pd.concat([y_aligned.rename("y_true"), pred_df], axis=1)

    # Add DCC-GARCH benchmark (one-step ahead) in the same target space if possible
    if bool(cfg.get("use_dcc_garch", True)) and DCC_AVAILABLE:
        try:
            dcc_pred, dcc_true = dcc_garch_fit_predict(
                r1=returns[base].loc[out_df.index],
                r2=returns[other].loc[out_df.index],
                horizon=horizon,
            )
            # Align lengths
            dcc_s = pd.Series(dcc_pred, index=out_df.index, name="DCC_GARCH")
            # Optionally move to fisher space
            if use_fisher:
                dcc_s = fisher_z(dcc_s)
            out_df["DCC_GARCH"] = dcc_s
        except Exception as e:
            warnings.warn(f"DCC benchmark failed for {dep_name}: {e}")

    out_df.to_csv(pred_out, encoding="utf-8")

    # Plot actual vs top preds
    fig_out = os.path.join(paths.figures, f"{dep_name}_w{window}_{target_space}.png")
    title = f"Forecasting time-varying dependency: {dep_name} (h={horizon}, w={window}, space={target_space})"
    save_plot_actual_vs_preds(y_aligned, out_df.drop(columns=["y_true"]), fig_out, title=title, top_k=3)

    # Window sensitivity plot (raw correlation only, independent of fisher)
    # We'll save once per pair in run_pipeline()

    # DM tests: compare best ML to Naive and to DCC if exists
    dm_rows = []
    # pick best ML model by RMSE excluding baselines
    candidate_cols = [c for c in out_df.columns if c not in ["y_true", "Naive_Last", "AR1", "DCC_GARCH"]]
    # ensure predictions exist
    rmse_map = {}
    for c in candidate_cols:
        m = ~out_df[c].isna()
        if m.sum() > 50:
            rmse_map[c] = _rmse(out_df.loc[m, "y_true"].values, out_df.loc[m, c].values)
    best_model = min(rmse_map, key=rmse_map.get) if rmse_map else None

    if best_model is not None:
        # vs Naive
        e_best = (out_df["y_true"] - out_df[best_model]).values
        e_naive = (out_df["y_true"] - out_df["Naive_Last"]).values
        dm = diebold_mariano(e_model=e_best, e_bench=e_naive, h=horizon, power=2, nw_lag=int(cfg.get("dm_nw_lag", 0)))
        dm_rows.append({"dependency": dep_name, "window": window, "space": target_space, "model": best_model, "benchmark": "Naive_Last", **dm})

        # vs DCC
        if "DCC_GARCH" in out_df.columns:
            e_dcc = (out_df["y_true"] - out_df["DCC_GARCH"]).values
            dm2 = diebold_mariano(e_model=e_best, e_bench=e_dcc, h=horizon, power=2, nw_lag=int(cfg.get("dm_nw_lag", 0)))
            dm_rows.append({"dependency": dep_name, "window": window, "space": target_space, "model": best_model, "benchmark": "DCC_GARCH", **dm2})

    dm_df = pd.DataFrame(dm_rows)

    # Add experiment columns to metrics
    if not metrics_df.empty:
        metrics_df.insert(0, "target_space", target_space)
        metrics_df.insert(0, "window", window)
        metrics_df.insert(0, "dependency", dep_name)

    return out_df, metrics_df, dm_df


def run_pipeline(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    paths = build_paths(cfg["base_dir"])
    _ensure_dirs(paths)

    tickers = cfg["assets"]["crypto"] + cfg["assets"]["traditional"]
    prices = fetch_prices_csv(paths, tickers, cfg["start_date"], cfg["end_date"])
    rets = compute_returns_csv(paths, prices)

    # dataset diagnostics for thesis figures
    describe_dataset(prices, rets, paths)
    write_run_metadata(paths, cfg)

    base = cfg.get("base_asset", "BTC-USD")
    others = cfg["assets"]["traditional"] + cfg.get("extra_assets", ["ETH-USD"])
    horizon = int(cfg.get("forecast_horizon", 1))

    windows = cfg.get("rolling_windows", None)
    if windows is None:
        windows = [int(cfg.get("rolling_window", 30))]

    use_fisher = bool(cfg.get("use_fisher_transform", True))

    all_metrics = []
    all_dm = []

    for other in others:
        if other not in rets.columns or base not in rets.columns or other == base:
            continue

        # sensitivity plot for rolling correlation windows (raw corr)
        series_dict = {}
        for w in windows:
            s = rolling_corr(rets[base], rets[other], int(w)).dropna()
            series_dict[f"w={w}"] = s
        sens_path = os.path.join(paths.figures, f"sensitivity_corr_{base}_{other}.png")
        save_plot_series(sens_path, f"Rolling correlation sensitivity: {base} vs {other}", series_dict, figsize=(12,5))

        for w in windows:
            pred_out, metrics_df, dm_df = run_single_experiment(
                returns=rets,
                paths=paths,
                cfg=cfg,
                base=base,
                other=other,
                window=int(w),
                horizon=horizon,
                use_fisher=use_fisher
            )
            if not metrics_df.empty:
                all_metrics.append(metrics_df)
            if not dm_df.empty:
                all_dm.append(dm_df)

            best_rmse = metrics_df.iloc[0]["RMSE"] if not metrics_df.empty else "n/a"
            print(f"Done: corr_{base}_{other} | w={w} | best RMSE: {best_rmse}")

    if all_metrics:
        metrics_all = pd.concat(all_metrics, axis=0).reset_index(drop=True)
        metrics_path = os.path.join(paths.results, "metrics.csv")
        metrics_all.to_csv(metrics_path, index=False, encoding="utf-8")

        # Produce LaTeX table snippet
        tex_path = os.path.join(paths.tables, "metrics_table.tex")
        metrics_to_latex(metrics_all.sort_values(["dependency", "window", "RMSE"]).head(40), tex_path,
                         caption="Out-of-sample forecasting metrics (target in Fisher-z space unless stated otherwise).")
        print(f"\nSaved metrics -> {metrics_path}")
        print(f"Saved LaTeX table -> {tex_path}")
    else:
        print("\nNo metrics saved (not enough test points).")

    if all_dm:
        dm_all = pd.concat(all_dm, axis=0).reset_index(drop=True)
        dm_path = os.path.join(paths.results, "dm_tests.csv")
        dm_all.to_csv(dm_path, index=False, encoding="utf-8")
        print(f"Saved DM tests -> {dm_path}")

    # Inform about DCC availability
    if bool(cfg.get("use_dcc_garch", True)) and not DCC_AVAILABLE:
        print("\nNOTE: DCC-GARCH benchmark was requested but is not available. Install 'arch' and dependencies:\n"
              "  python -m pip install arch\n"
              "Then re-run.")
