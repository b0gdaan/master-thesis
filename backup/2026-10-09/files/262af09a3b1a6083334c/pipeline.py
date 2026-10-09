"""
Main pipeline for Intermarket Dependency Forecasting.
Handles: data download → rolling correlations → feature engineering →
         walk-forward ML training → DCC benchmark → metrics → DM tests → figures.
"""
import os
import sys
import json
import warnings
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import yaml
import numpy as np
import pandas as pd
import yfinance as yf

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from sklearn.linear_model import Ridge, LinearRegression, ElasticNet
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy import stats

# ── XGBoost ──────────────────────────────────────────────────────────────────
try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False

# ── DCC-GARCH ─────────────────────────────────────────────────────────────────
try:
    from thesis_app.dcc import dcc_garch_fit_predict
    DCC_AVAILABLE = True
except Exception:
    try:
        from dcc import dcc_garch_fit_predict  # fallback for notebooks
        DCC_AVAILABLE = True
    except Exception:
        DCC_AVAILABLE = False


# ═════════════════════════════════════════════════════════════════════════════
# Paths
# ═════════════════════════════════════════════════════════════════════════════
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
    notebooks: str


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
        notebooks=os.path.join(base_dir, "notebooks"),
    )


def ensure_dirs(paths: Paths) -> None:
    for d in vars(paths).values():
        if d and d != paths.base_dir:
            os.makedirs(d, exist_ok=True)


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ═════════════════════════════════════════════════════════════════════════════
# Data
# ═════════════════════════════════════════════════════════════════════════════
def _pick_close(df: pd.DataFrame) -> pd.DataFrame:
    """Extract Close/Adj Close panel from yfinance MultiIndex or flat DataFrame."""
    if isinstance(df.columns, pd.MultiIndex):
        lv0 = df.columns.get_level_values(0)
        for field_name in ("Adj Close", "Close"):
            if field_name in lv0:
                return df[field_name]
        raise KeyError(f"No Close field found. Available: {sorted(set(lv0))}")
    for field_name in ("Adj Close", "Close"):
        if field_name in df.columns:
            return df[[field_name]]
    raise KeyError("No Close field found.")


def fetch_prices(paths: Paths, tickers: List[str], start: str, end: Optional[str]) -> pd.DataFrame:
    prices_path = os.path.join(paths.data_raw, "prices.csv")
    if os.path.exists(prices_path):
        df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
        missing = [t for t in tickers if t not in df.columns]
        if not missing:
            print(f"Loaded prices from cache: {prices_path}")
            return df
        print(f"Re-downloading: missing tickers {missing}")

    print(f"Downloading {len(tickers)} tickers from Yahoo Finance...")
    dl = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        group_by="column",
        progress=True,
        threads=True,
    )
    prices = _pick_close(dl)
    # Drop rows with all NaN then forward-fill minimal gaps
    prices = prices.dropna(how="all").ffill(limit=2).dropna()
    prices.to_csv(prices_path, encoding="utf-8")
    print(f"Saved prices: {prices_path}  shape={prices.shape}")
    return prices


def compute_returns(paths: Paths, prices: pd.DataFrame) -> pd.DataFrame:
    ret_path = os.path.join(paths.data_processed, "returns.csv")
    if os.path.exists(ret_path):
        return pd.read_csv(ret_path, index_col=0, parse_dates=True)
    rets = np.log(prices / prices.shift(1)).dropna()
    rets.to_csv(ret_path, encoding="utf-8")
    return rets


# ═════════════════════════════════════════════════════════════════════════════
# Transforms
# ═════════════════════════════════════════════════════════════════════════════
def fisher_z(r: pd.Series, eps: float = 1e-6) -> pd.Series:
    """Fisher z-transform: z = arctanh(r). Stabilizes variance of correlations."""
    return np.arctanh(r.clip(-1 + eps, 1 - eps))


def inv_fisher_z(z) -> pd.Series:
    return np.tanh(z)


def rolling_corr(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    return a.rolling(window).corr(b)


# ═════════════════════════════════════════════════════════════════════════════
# Target & Features
# ═════════════════════════════════════════════════════════════════════════════
def build_target(
    returns: pd.DataFrame,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool,
) -> pd.Series:
    """
    Target: rolling correlation at t+h.
    Optionally Fisher-z transformed.
    """
    corr = rolling_corr(returns[base], returns[other], window).dropna()
    y = corr.shift(-horizon).dropna()
    return fisher_z(y) if use_fisher else y


def build_features(
    returns: pd.DataFrame,
    window: int,
    y_target: pd.Series,
    base: str,
    other: str,
    horizon: int,
) -> pd.DataFrame:
    """
    Feature set at time t to forecast y(t+h):
    - lags 1,2,5 of current dependency (in same z-space)
    - rolling vol (base & other)
    - lagged returns (lag 1,2,5 for both assets)
    - rolling mean returns (trend proxy)
    - VIX-like spread proxy: |r_base - r_other|
    """
    idx = y_target.index
    X = pd.DataFrame(index=idx)

    # Reconstruct "current" y (un-shifted) as lag features
    y_current = y_target.shift(+horizon).reindex(idx)
    for lag in [1, 2, 5, 10]:
        X[f"dep_lag{lag}"] = y_current.shift(lag)

    # Rolling vol
    X["vol_base"] = returns[base].rolling(window).std().reindex(idx)
    X["vol_other"] = returns[other].rolling(window).std().reindex(idx)

    # Lagged returns
    for lag in [1, 2, 5]:
        X[f"r_base_lag{lag}"] = returns[base].shift(lag).reindex(idx)
        X[f"r_other_lag{lag}"] = returns[other].shift(lag).reindex(idx)

    # Rolling mean (trend)
    X["mean_base"] = returns[base].rolling(window).mean().reindex(idx)
    X["mean_other"] = returns[other].rolling(window).mean().reindex(idx)

    # Cross-asset spread proxy
    X["abs_spread"] = (returns[base] - returns[other]).abs().rolling(5).mean().reindex(idx)

    # Realized correlation change proxy
    corr_short = rolling_corr(returns[base], returns[other], max(5, window // 4)).reindex(idx)
    corr_long = rolling_corr(returns[base], returns[other], window).reindex(idx)
    X["corr_diff"] = (corr_short - corr_long).reindex(idx)

    return X.dropna()


# ═════════════════════════════════════════════════════════════════════════════
# Walk-forward evaluation
# ═════════════════════════════════════════════════════════════════════════════
def _make_xgb(device: str, random_state: int) -> Optional[object]:
    if not XGB_AVAILABLE:
        return None
    try:
        # XGBoost ≥2.0: use device="cuda" or device="cpu"
        return xgb.XGBRegressor(
            n_estimators=1000,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            device=device,
            random_state=random_state,
            verbosity=0,
        )
    except TypeError:
        # Older XGBoost fallback
        tree_method = "gpu_hist" if device == "cuda" else "hist"
        return xgb.XGBRegressor(
            n_estimators=1000,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method=tree_method,
            random_state=random_state,
            verbosity=0,
        )


def fit_predict_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int,
    refit_every: int,
    random_state: int,
    use_xgb: bool,
    xgb_device: str = "cuda",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Walk-forward (expanding window) prediction with periodic refit.
    Returns (pred_df, metrics_df).
    """
    Xv = X.values
    idx = X.index
    yv = y.loc[idx].values
    n = len(idx)

    model_specs: Dict[str, Optional[object]] = {
        "Naive_Last": None,
        "AR1": LinearRegression(),
        "ElasticNet": ElasticNet(alpha=0.01, l1_ratio=0.5, random_state=random_state, max_iter=5000),
        "Ridge": Ridge(alpha=1.0),
        "RF": RandomForestRegressor(n_estimators=300, max_depth=8, random_state=random_state, n_jobs=-1),
        "GBM": GradientBoostingRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=random_state),
    }

    if use_xgb and XGB_AVAILABLE:
        xgb_model = _make_xgb(xgb_device, random_state)
        if xgb_model is not None:
            key = f"XGB_{'GPU' if xgb_device == 'cuda' else 'CPU'}"
            model_specs[key] = xgb_model

    preds = {name: np.full(n, np.nan, dtype=float) for name in model_specs}
    y_series = pd.Series(yv, index=idx)
    fitted: Dict[str, object] = {}
    last_refit = -10**9

    for t in range(min_train, n):
        tr = np.arange(0, t)

        should_refit = (t - last_refit) >= refit_every
        if should_refit:
            last_refit = t
            X_tr, y_tr = Xv[tr], yv[tr]

            # AR(1): use dep_lag1 as the single feature
            ar_y = y_series.iloc[tr].values
            ar_X = y_series.iloc[tr].shift(1).values.reshape(-1, 1)
            valid = ~np.isnan(ar_X[:, 0])
            if valid.sum() > 10:
                try:
                    model_specs["AR1"].fit(ar_X[valid], ar_y[valid])
                    fitted["AR1"] = model_specs["AR1"]
                except Exception:
                    pass

            for name, m in model_specs.items():
                if m is None or name == "AR1":
                    continue
                try:
                    m.fit(X_tr, y_tr)
                    fitted[name] = m
                except Exception as e:
                    warnings.warn(f"Fit failed for {name} at t={t}: {e}")

        # Naive persistence
        if t > 0 and not np.isnan(yv[t - 1]):
            preds["Naive_Last"][t] = yv[t - 1]

        # AR(1)
        if "AR1" in fitted and not np.isnan(yv[t - 1]):
            try:
                preds["AR1"][t] = fitted["AR1"].predict([[yv[t - 1]]])[0]
            except Exception:
                pass

        # ML models
        for name in list(fitted.keys()):
            if name == "AR1":
                continue
            try:
                preds[name][t] = fitted[name].predict(Xv[t:t + 1])[0]
            except Exception:
                pass

    pred_df = pd.DataFrame(preds, index=idx)

    # Metrics
    rows = []
    for name in pred_df.columns:
        mask = pred_df[name].notna()
        if mask.sum() < 50:
            continue
        yt = y.loc[idx][mask].values
        yp = pred_df.loc[mask, name].values
        rows.append({
            "model": name,
            "MAE": float(mean_absolute_error(yt, yp)),
            "RMSE": float(np.sqrt(mean_squared_error(yt, yp))),
            "R2": float(r2_score(yt, yp)),
            "n_test": int(mask.sum()),
        })

    metrics_df = pd.DataFrame(rows).sort_values("RMSE").reset_index(drop=True)
    return pred_df, metrics_df


# ═════════════════════════════════════════════════════════════════════════════
# Diebold–Mariano test
# ═════════════════════════════════════════════════════════════════════════════
def diebold_mariano(
    e_model: np.ndarray,
    e_bench: np.ndarray,
    h: int = 1,
    power: int = 2,
    nw_lag: int = 0,
) -> Dict:
    """
    DM test: d_t = |e_bench|^p - |e_model|^p.
    Positive DM-stat → model better than benchmark.
    """
    e_model = np.asarray(e_model, dtype=float)
    e_bench = np.asarray(e_bench, dtype=float)
    mask = np.isfinite(e_model) & np.isfinite(e_bench)
    e_model, e_bench = e_model[mask], e_bench[mask]
    T = len(e_model)
    if T < 30:
        return {"DM_stat": np.nan, "p_value": np.nan, "n": T}

    d = (np.abs(e_bench) ** power) - (np.abs(e_model) ** power)
    d_mean = d.mean()

    # Newey–West variance
    var = np.var(d, ddof=1)
    for lag in range(1, nw_lag + 1):
        cov = np.cov(d[lag:], d[:-lag], ddof=1)[0, 1]
        w = 1.0 - lag / (nw_lag + 1.0)
        var += 2 * w * cov

    dm = d_mean / math.sqrt(var / T) if var > 0 else np.nan
    p = 2 * (1 - stats.t.cdf(abs(dm), df=T - 1)) if np.isfinite(dm) else np.nan
    return {"DM_stat": float(dm) if np.isfinite(dm) else None,
            "p_value": float(p) if np.isfinite(p) else None,
            "n": T}


# ═════════════════════════════════════════════════════════════════════════════
# Plotting helpers
# ═════════════════════════════════════════════════════════════════════════════
def plot_series(out_path: str, title: str, series_dict: Dict[str, pd.Series], figsize=(12, 5)) -> None:
    plt.figure(figsize=figsize)
    for label, s in series_dict.items():
        plt.plot(s.index, s.values, label=label, linewidth=1)
    plt.title(title)
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def plot_forecast(y: pd.Series, pred_df: pd.DataFrame, out_path: str, title: str, top_k: int = 4) -> None:
    plt.figure(figsize=(13, 5))
    plt.plot(y.index, y.values, label="Actual", linewidth=1.8, color="black")
    cols = [c for c in pred_df.columns if pred_df[c].notna().sum() > 50]
    colors = plt.cm.tab10.colors
    for i, c in enumerate(cols[:top_k]):
        plt.plot(pred_df.index, pred_df[c].values, label=c, alpha=0.85, linewidth=1, color=colors[i])
    plt.legend(ncol=2)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


# ═════════════════════════════════════════════════════════════════════════════
# Dataset diagnostics
# ═════════════════════════════════════════════════════════════════════════════
def describe_dataset(prices: pd.DataFrame, returns: pd.DataFrame, paths: Paths, cfg: Dict) -> None:
    # Prices
    fig, ax = plt.subplots(figsize=(13, 6))
    for c in prices.columns:
        normed = prices[c] / prices[c].iloc[0]
        ax.plot(prices.index, normed, label=c, linewidth=1)
    ax.set_title("Normalized prices (Yahoo Finance, adjusted close)")
    ax.legend(loc="best", ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_prices.png"), dpi=120)
    plt.close()

    # Rolling volatility
    fig, ax = plt.subplots(figsize=(13, 5))
    roll = returns.rolling(30).std()
    for c in roll.columns:
        ax.plot(roll.index, roll[c], label=c, linewidth=1)
    ax.set_title("30-day rolling volatility of log-returns")
    ax.legend(loc="best", ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_volatility.png"), dpi=120)
    plt.close()

    # Correlation heatmap
    corr = returns.corr()
    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index, fontsize=9)
    ax.set_title("Full-sample correlation matrix (log-returns)")
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_corr_heatmap.png"), dpi=120)
    plt.close()

    # Return distribution
    fig, axes = plt.subplots(2, 4, figsize=(16, 7))
    for i, c in enumerate(returns.columns[:8]):
        ax = axes[i // 4, i % 4]
        ax.hist(returns[c].dropna(), bins=80, edgecolor="none", color="#2077b4", alpha=0.8)
        ax.set_title(c, fontsize=9)
        ax.set_xlabel("log-return")
    plt.suptitle("Return distributions", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_return_dist.png"), dpi=120)
    plt.close()

    # Summary JSON
    summary = {
        "n_days_prices": int(len(prices)),
        "n_days_returns": int(len(returns)),
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
        "tickers": list(prices.columns),
    }
    with open(os.path.join(paths.results, "dataset_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


def write_metadata(paths: Paths, cfg: Dict) -> None:
    meta = {"python": sys.version, "config": cfg}
    try:
        import importlib.metadata as md
        meta["packages"] = {}
        for pkg in ["numpy", "pandas", "scikit-learn", "scipy", "yfinance", "xgboost", "arch"]:
            try:
                meta["packages"][pkg] = md.version(pkg)
            except Exception:
                pass
    except Exception:
        pass
    with open(os.path.join(paths.results, "run_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)


# ═════════════════════════════════════════════════════════════════════════════
# LaTeX export
# ═════════════════════════════════════════════════════════════════════════════
def metrics_to_latex(df: pd.DataFrame, out_tex: str, caption: str, label: str) -> None:
    if df.empty:
        return
    needed = ["dependency", "window", "target_space", "model", "MAE", "RMSE", "R2", "n_test"]
    for c in needed:
        if c not in df.columns:
            df = df.copy()
            df[c] = ""
    df = df[needed].copy()
    for c in ["MAE", "RMSE", "R2"]:
        df[c] = df[c].apply(lambda x: f"{float(x):.4f}")
    df["n_test"] = df["n_test"].astype(str)

    lines = [
        r"\begin{table}[H]", r"\centering", r"\small",
        r"\caption{" + caption + "}",
        r"\label{" + label + "}",
        r"\begin{tabular}{llllrrrr}",
        r"\toprule",
        r"Dependency & $w$ & Space & Model & MAE & RMSE & $R^2$ & $n$ \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"{row['dependency']} & {row['window']} & {row['target_space']} & "
            f"{row['model']} & {row['MAE']} & {row['RMSE']} & {row['R2']} & {row['n_test']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def dm_to_latex(df: pd.DataFrame, out_tex: str) -> None:
    if df.empty:
        return
    lines = [
        r"\begin{table}[H]", r"\centering", r"\small",
        r"\caption{Diebold--Mariano tests for equal predictive accuracy}",
        r"\label{tab:dm_tests}",
        r"\begin{tabular}{llllrrl}",
        r"\toprule",
        r"Dependency & $w$ & Model & Benchmark & DM stat & $p$-value & Sign \\",
        r"\midrule",
    ]
    for _, r in df.iterrows():
        dm = r.get("DM_stat", "")
        pv = r.get("p_value", "")
        try:
            dm_f = f"{float(dm):.2f}"
            pv_f = f"{float(pv):.4f}"
            sign = "***" if float(pv) < 0.01 else ("**" if float(pv) < 0.05 else ("*" if float(pv) < 0.1 else ""))
        except Exception:
            dm_f, pv_f, sign = str(dm), str(pv), ""
        lines.append(
            f"{r.get('dependency','')} & {r.get('window','')} & {r.get('model','')} & "
            f"{r.get('benchmark','')} & {dm_f} & {pv_f} & {sign} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# Single experiment runner
# ═════════════════════════════════════════════════════════════════════════════
def run_experiment(
    returns: pd.DataFrame,
    paths: Paths,
    cfg: Dict,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    dep_name = f"corr_{base}_{other}"
    target_space = "fisher_z" if use_fisher else "raw_corr"

    y = build_target(returns, base, other, window, horizon, use_fisher)
    X = build_features(returns, window, y, base, other, horizon)
    y_aln = y.loc[X.index]

    pred_df, metrics_df = fit_predict_walk_forward(
        X=X, y=y_aln,
        min_train=int(cfg["min_train_size"]),
        refit_every=int(cfg["refit_every"]),
        random_state=int(cfg["random_state"]),
        use_xgb=bool(cfg.get("use_xgboost", True)),
        xgb_device=str(cfg.get("xgb_device", "cuda")),
    )

    out_df = pd.concat([y_aln.rename("y_true"), pred_df], axis=1)

    # DCC-GARCH benchmark
    if bool(cfg.get("use_dcc_garch", True)) and DCC_AVAILABLE:
        try:
            r1 = returns[base].loc[out_df.index]
            r2 = returns[other].loc[out_df.index]
            dcc_pred, _ = dcc_garch_fit_predict(r1, r2, horizon=horizon)
            dcc_s = pd.Series(dcc_pred, index=out_df.index)
            if use_fisher:
                dcc_s = fisher_z(dcc_s)
            out_df["DCC_GARCH"] = dcc_s
        except Exception as exc:
            warnings.warn(f"DCC failed for {dep_name} w={window}: {exc}")

    # Save predictions
    pred_csv = os.path.join(paths.predictions, f"{dep_name}_w{window}_{target_space}_predictions.csv")
    out_df.to_csv(pred_csv, encoding="utf-8")

    # Forecast plot
    fig_path = os.path.join(paths.figures, f"{dep_name}_w{window}_{target_space}.png")
    plot_forecast(
        y_aln, out_df.drop(columns=["y_true"]),
        fig_path,
        title=f"Forecasting: {dep_name} | h={horizon} | w={window} | {target_space}",
        top_k=4,
    )

    # DM tests
    dm_rows = []
    candidates = [c for c in out_df.columns if c not in ("y_true", "Naive_Last", "AR1", "DCC_GARCH")]
    rmse_map = {}
    for c in candidates:
        mask = out_df[c].notna()
        if mask.sum() > 50:
            rmse_map[c] = float(np.sqrt(mean_squared_error(
                out_df.loc[mask, "y_true"], out_df.loc[mask, c]
            )))
    best = min(rmse_map, key=rmse_map.get) if rmse_map else None

    if best:
        e_best = (out_df["y_true"] - out_df[best]).values
        for bench in ["Naive_Last", "DCC_GARCH"]:
            if bench in out_df.columns:
                e_b = (out_df["y_true"] - out_df[bench]).values
                dm = diebold_mariano(e_best, e_b, h=horizon, nw_lag=int(cfg.get("dm_nw_lag", 0)))
                dm_rows.append({
                    "dependency": dep_name, "window": window, "space": target_space,
                    "model": best, "benchmark": bench, **dm,
                })

    dm_df = pd.DataFrame(dm_rows)

    if not metrics_df.empty:
        metrics_df.insert(0, "target_space", target_space)
        metrics_df.insert(0, "window", window)
        metrics_df.insert(0, "dependency", dep_name)

    return out_df, metrics_df, dm_df


# ═════════════════════════════════════════════════════════════════════════════
# Main pipeline
# ═════════════════════════════════════════════════════════════════════════════
def run_pipeline(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    paths = build_paths(cfg["base_dir"])
    ensure_dirs(paths)

    tickers = cfg["assets"]["crypto"] + cfg["assets"]["traditional"]
    prices = fetch_prices(paths, tickers, cfg["start_date"], cfg.get("end_date"))
    rets = compute_returns(paths, prices)

    describe_dataset(prices, rets, paths, cfg)
    write_metadata(paths, cfg)

    base = cfg.get("base_asset", "BTC-USD")
    others = cfg["assets"]["traditional"] + cfg.get("extra_assets", [])
    # Deduplicate and exclude base from others
    others = list(dict.fromkeys([o for o in others if o != base]))
    horizon = int(cfg.get("forecast_horizon", 1))
    windows = [int(w) for w in cfg.get("rolling_windows", [30])]
    use_fisher = bool(cfg.get("use_fisher_transform", True))

    all_metrics = []
    all_dm = []

    for other in others:
        if other not in rets.columns:
            print(f"Skip {other}: not in returns data.")
            continue

        # Window sensitivity plot
        sens = {f"w={w}": rolling_corr(rets[base], rets[other], w).dropna() for w in windows}
        plot_series(
            os.path.join(paths.figures, f"sensitivity_{base}_{other}.png"),
            f"Rolling correlation sensitivity: {base} vs {other}",
            sens,
        )

        for w in windows:
            print(f"\n▶ {base} vs {other} | w={w} | fisher={use_fisher}")
            try:
                out_df, met, dm = run_experiment(
                    returns=rets, paths=paths, cfg=cfg,
                    base=base, other=other, window=w,
                    horizon=horizon, use_fisher=use_fisher,
                )
                if not met.empty:
                    all_metrics.append(met)
                if not dm.empty:
                    all_dm.append(dm)
                best_row = met.iloc[0] if not met.empty else None
                if best_row is not None:
                    print(f"  Best: {best_row['model']}  RMSE={best_row['RMSE']:.4f}  R2={best_row['R2']:.3f}")
            except Exception as e:
                warnings.warn(f"Experiment failed for {base} vs {other} w={w}: {e}")
                import traceback
                traceback.print_exc()

    # Save aggregate results
    if all_metrics:
        metrics_all = pd.concat(all_metrics).reset_index(drop=True)
        mpath = os.path.join(paths.results, "metrics.csv")
        metrics_all.to_csv(mpath, index=False)
        print(f"\n✓ metrics.csv → {mpath}")

        tex = os.path.join(paths.tables, "metrics_table.tex")
        metrics_to_latex(
            metrics_all.sort_values(["dependency", "window", "RMSE"]).head(60),
            tex,
            caption="Out-of-sample forecasting metrics (Fisher-z space).",
            label="tab:metrics",
        )
        print(f"✓ metrics_table.tex → {tex}")

    if all_dm:
        dm_all = pd.concat(all_dm).reset_index(drop=True)
        dpath = os.path.join(paths.results, "dm_tests.csv")
        dm_all.to_csv(dpath, index=False)
        print(f"✓ dm_tests.csv → {dpath}")

        dm_tex = os.path.join(paths.tables, "dm_tests.tex")
        dm_to_latex(dm_all, dm_tex)
        print(f"✓ dm_tests.tex → {dm_tex}")

    print("\n✅ Pipeline complete.")
    if bool(cfg.get("use_dcc_garch", True)) and not DCC_AVAILABLE:
        print("⚠  DCC-GARCH was requested but 'arch' package not found. Run: pip install arch")
