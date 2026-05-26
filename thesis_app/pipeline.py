"""
Main pipeline for intermarket dependency forecasting.
Handles data download, feature engineering, walk-forward ML training,
DCC benchmark evaluation, metrics, DM tests, and figures.
"""
import json
import math
import multiprocessing
import os
import shutil
import sys
import threading
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
import yfinance as yf
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False

try:
    from thesis_app.dcc_walk import dcc_garch_walk_forward_predict
    DCC_AVAILABLE = True
except Exception:
    try:
        from dcc_walk import dcc_garch_walk_forward_predict
        DCC_AVAILABLE = True
    except Exception:
        DCC_AVAILABLE = False

try:
    from thesis_app.signal_layer import run_signal_experiment, signal_metrics_to_latex
except Exception:
    from signal_layer import run_signal_experiment, signal_metrics_to_latex


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
    paths = Paths(
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
    ensure_dirs(paths)
    return paths


def ensure_dirs(paths: Paths) -> None:
    for directory in vars(paths).values():
        if directory and directory != paths.base_dir:
            os.makedirs(directory, exist_ok=True)


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _pick_close(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        level0 = df.columns.get_level_values(0)
        for field_name in ("Adj Close", "Close"):
            if field_name in level0:
                return df[field_name]
        raise KeyError(f"No close field found. Available: {sorted(set(level0))}")

    for field_name in ("Adj Close", "Close"):
        if field_name in df.columns:
            return df[[field_name]]
    raise KeyError("No close field found.")


def fetch_prices(paths: Paths, tickers: List[str], start: str, end: Optional[str]) -> pd.DataFrame:
    prices_path = os.path.join(paths.data_raw, "prices.csv")
    if os.path.exists(prices_path):
        cached = pd.read_csv(prices_path, index_col=0, parse_dates=True)
        missing = [ticker for ticker in tickers if ticker not in cached.columns]
        if not missing:
            required_end = pd.Timestamp(end) if end else pd.Timestamp.today()
            cache_covers = (
                cached.index.min() <= pd.Timestamp(start)
                and cached.index.max() >= required_end - pd.Timedelta(days=7)
            )
            if cache_covers:
                print(f"Loaded prices from cache: {prices_path}")
                return cached.sort_index()
            print("Re-downloading: cached date range does not cover config dates.")
        else:
            print(f"Re-downloading because cache is missing tickers: {missing}")

    print(f"Downloading {len(tickers)} tickers from Yahoo Finance...")
    downloaded = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        group_by="column",
        progress=True,
        threads=True,
    )
    prices = _pick_close(downloaded)
    prices = prices.dropna(how="all").ffill(limit=2).dropna().sort_index()
    os.makedirs(os.path.dirname(prices_path), exist_ok=True)
    prices.to_csv(prices_path, encoding="utf-8")
    print(f"Saved prices: {prices_path} shape={prices.shape}")
    return prices


def compute_returns(paths: Paths, prices: pd.DataFrame) -> pd.DataFrame:
    ret_path = os.path.join(paths.data_processed, "returns.csv")
    returns = np.log(prices / prices.shift(1)).dropna().sort_index()

    if os.path.exists(ret_path):
        cached = pd.read_csv(ret_path, index_col=0, parse_dates=True)
        same_columns = list(cached.columns) == list(returns.columns)
        same_index = cached.index.equals(returns.index)
        if same_columns and same_index:
            return cached
        print("Recomputing returns.csv because cache does not match current prices.csv")

    os.makedirs(os.path.dirname(ret_path), exist_ok=True)
    returns.to_csv(ret_path, encoding="utf-8")
    return returns


def fisher_z(r: pd.Series, eps: float = 1e-6) -> pd.Series:
    return np.arctanh(r.clip(-1 + eps, 1 - eps))


def inv_fisher_z(z):
    return np.tanh(z)


def rolling_corr(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    return a.rolling(window).corr(b)


def build_target(
    returns: pd.DataFrame,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool,
) -> pd.Series:
    corr = rolling_corr(returns[base], returns[other], window).dropna()
    target = corr.shift(-horizon).dropna()
    return fisher_z(target) if use_fisher else target


def build_features(
    returns: pd.DataFrame,
    window: int,
    y_target: pd.Series,
    base: str,
    other: str,
    horizon: int,
) -> pd.DataFrame:
    idx = y_target.index
    features = pd.DataFrame(index=idx)

    # ── Dependency lags (extended: monthly + quarterly) ──────────────────────
    y_current = y_target.shift(horizon).reindex(idx)
    for lag in [1, 2, 5, 10, 20, 60]:
        features[f"dep_lag{lag}"] = y_current.shift(lag)

    # ── Dependency momentum (trend of the correlation series) ────────────────
    features["dep_mom_5"]  = y_current.diff(5).reindex(idx)
    features["dep_mom_20"] = y_current.diff(20).reindex(idx)

    # ── Dependency regime: z-score relative to trailing 252-day history ──────
    dep_roll_mean = y_current.rolling(252, min_periods=60).mean()
    dep_roll_std  = y_current.rolling(252, min_periods=60).std()
    features["dep_zscore"] = ((y_current - dep_roll_mean) / (dep_roll_std + 1e-8)).reindex(idx)

    # ── Volatility (two windows) ──────────────────────────────────────────────
    features["vol_base"]    = returns[base].rolling(window).std().reindex(idx)
    features["vol_other"]   = returns[other].rolling(window).std().reindex(idx)
    features["vol_base_60"] = returns[base].rolling(60).std().reindex(idx)
    features["vol_other_60"] = returns[other].rolling(60).std().reindex(idx)
    features["vol_ratio"]   = (features["vol_base"] / (features["vol_other"] + 1e-10)).reindex(idx)

    # ── Return lags (extended) ────────────────────────────────────────────────
    for lag in [1, 2, 5, 10, 20]:
        features[f"r_base_lag{lag}"]  = returns[base].shift(lag).reindex(idx)
        features[f"r_other_lag{lag}"] = returns[other].shift(lag).reindex(idx)

    # ── Rolling mean returns ──────────────────────────────────────────────────
    features["mean_base"]  = returns[base].rolling(window).mean().reindex(idx)
    features["mean_other"] = returns[other].rolling(window).mean().reindex(idx)

    # ── Dispersion features ───────────────────────────────────────────────────
    features["abs_spread"]    = (returns[base] - returns[other]).abs().rolling(5).mean().reindex(idx)
    features["abs_spread_20"] = (returns[base] - returns[other]).abs().rolling(20).mean().reindex(idx)

    # ── Multi-scale correlation structure ─────────────────────────────────────
    corr_short = rolling_corr(returns[base], returns[other], max(5, window // 4)).reindex(idx)
    corr_long  = rolling_corr(returns[base], returns[other], window).reindex(idx)
    features["corr_diff"] = corr_short - corr_long

    # Velocity: how fast is the short-run correlation changing
    features["corr_short_mom"] = corr_short.diff(5).reindex(idx)

    # ── Base asset squared return (volatility proxy, no look-ahead) ──────────
    features["r_base_sq_lag1"]  = (returns[base].shift(1) ** 2).reindex(idx)
    features["r_other_sq_lag1"] = (returns[other].shift(1) ** 2).reindex(idx)

    return features.dropna()


def _make_xgb(device: str, random_state: int):
    if not XGB_AVAILABLE:
        return None

    common = dict(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.02,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        # random_state is the sklearn-compatible alias for XGBoost's `seed` parameter.
        # Both are set explicitly so results are reproducible across XGBoost API versions.
        random_state=random_state,
        seed=random_state,
        verbosity=0,
    )
    try:
        return xgb.XGBRegressor(device=device, **common)
    except TypeError:
        tree_method = "gpu_hist" if device == "cuda" else "hist"
        return xgb.XGBRegressor(tree_method=tree_method, **common)


# Cache the XGB device probe result so it only runs once per process even in
# parallel mode (ThreadPoolExecutor shares module-level state).
_XGB_DEVICE_CACHE: Optional[str] = None
_XGB_DEVICE_LOCK = threading.Lock()


def _probe_xgb_device(device: str, random_state: int) -> str:
    """Pre-flight test for XGBoost device availability.

    Trains a tiny model before the main walk-forward loop so that a CUDA
    failure is caught once and cleanly, rather than mid-loop with a noisy
    traceback. Returns the effective device string ('cuda' or 'cpu').

    Result is cached at module level so parallel workers never repeat the test.
    """
    global _XGB_DEVICE_CACHE
    if _XGB_DEVICE_CACHE is not None:
        return _XGB_DEVICE_CACHE
    with _XGB_DEVICE_LOCK:
        # Double-checked locking: re-test after acquiring lock
        if _XGB_DEVICE_CACHE is not None:
            return _XGB_DEVICE_CACHE
        if not XGB_AVAILABLE or device != "cuda":
            _XGB_DEVICE_CACHE = device
            return device
        try:
            _X = np.random.default_rng(0).random((30, 3)).astype("float32")
            _y = np.random.default_rng(0).random(30).astype("float32")
            _probe = _make_xgb("cuda", random_state)
            if _probe is not None:
                _probe.fit(_X, _y)
            warnings.warn(
                "Note: XGBoost GPU mode may produce non-bit-identical results across "
                "different hardware. For fully reproducible results set xgb_device: 'cpu' "
                "in config.yaml."
            )
            _XGB_DEVICE_CACHE = "cuda"
        except Exception as _exc:
            warnings.warn(
                f"XGBoost CUDA pre-flight test failed — falling back to CPU for all XGB models. "
                f"Reason: {_exc}"
            )
            _XGB_DEVICE_CACHE = "cpu"
    return _XGB_DEVICE_CACHE


def compute_prediction_metrics(y_true: pd.Series, pred_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model_name in pred_df.columns:
        mask = pred_df[model_name].notna() & y_true.notna()
        if int(mask.sum()) < 50:
            continue
        yt = y_true.loc[mask].values
        yp = pred_df.loc[mask, model_name].values
        rows.append(
            {
                "model": model_name,
                "MAE": float(mean_absolute_error(yt, yp)),
                "RMSE": float(np.sqrt(mean_squared_error(yt, yp))),
                "R2": float(r2_score(yt, yp)),
                "n_test": int(mask.sum()),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["model", "MAE", "RMSE", "R2", "n_test"])
    return pd.DataFrame(rows).sort_values("RMSE").reset_index(drop=True)


def compute_bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    random_state: int = 42,
) -> Dict:
    """Bootstrap confidence interval for RMSE and R2.

    Resamples (y_true, y_pred) pairs with replacement `n_bootstrap` times and
    computes the empirical percentile interval.  The result quantifies sampling
    uncertainty in the OOS metric estimate, not predictive uncertainty.

    Vectorised implementation: all bootstrap samples are drawn at once as a
    (n_bootstrap × n) index matrix, then RMSE and R² are computed with batched
    NumPy operations.  This is typically 20-50× faster than a Python loop.
    """
    rng = np.random.default_rng(random_state)
    n = len(y_true)

    # Draw all bootstrap indices at once: shape (n_bootstrap, n)
    boot_idx = rng.integers(0, n, size=(n_bootstrap, n))
    yt_b = y_true[boot_idx]   # (n_bootstrap, n)
    yp_b = y_pred[boot_idx]   # (n_bootstrap, n)

    residuals = yt_b - yp_b
    rmse_samples = np.sqrt(np.mean(residuals ** 2, axis=1))

    yt_mean = yt_b.mean(axis=1, keepdims=True)
    ss_res = np.sum(residuals ** 2, axis=1)
    ss_tot = np.sum((yt_b - yt_mean) ** 2, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        r2_samples = np.where(ss_tot > 0, 1.0 - ss_res / ss_tot, 0.0)

    alpha = (1.0 - ci) / 2.0
    return {
        "rmse_mean":     float(np.mean(rmse_samples)),
        "rmse_ci_lower": float(np.percentile(rmse_samples, 100 * alpha)),
        "rmse_ci_upper": float(np.percentile(rmse_samples, 100 * (1 - alpha))),
        "r2_mean":       float(np.mean(r2_samples)),
        "r2_ci_lower":   float(np.percentile(r2_samples, 100 * alpha)),
        "r2_ci_upper":   float(np.percentile(r2_samples, 100 * (1 - alpha))),
    }


def compute_metrics_with_ci(
    y_true: pd.Series,
    pred_df: pd.DataFrame,
    n_bootstrap: int = 1000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Compute OOS metrics with bootstrap 95 % confidence intervals.

    Saves columns: model, rmse_mean, rmse_ci_lower, rmse_ci_upper,
                   r2_mean, r2_ci_lower, r2_ci_upper, n_test.
    """
    rows = []
    for model_name in pred_df.columns:
        mask = pred_df[model_name].notna() & y_true.notna()
        if int(mask.sum()) < 50:
            continue
        yt = y_true.loc[mask].values
        yp = pred_df.loc[mask, model_name].values
        ci = compute_bootstrap_ci(yt, yp, n_bootstrap=n_bootstrap, random_state=random_state)
        rows.append({"model": model_name, "n_test": int(mask.sum()), **ci})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("rmse_mean").reset_index(drop=True)


def refit_sensitivity_analysis(
    returns: pd.DataFrame,
    paths: Paths,
    cfg: Dict,
    rep_base: str = "BTC-USD",
    rep_other: str = "^GSPC",
    rep_window: int = 30,
) -> None:
    """Sweep refit_every over several values for a representative pair.

    Uses the BTC-USD vs ^GSPC, w=30 pair as the representative case.
    Results are saved to outputs/results/refit_sensitivity.csv and
    outputs/figures/refit_sensitivity.png.

    Justification for default refit_every=20 (≈ monthly):
        Monthly model updates match the standard rebalancing frequency in
        institutional portfolio risk management (Grinold & Kahn 1999).
        More frequent refits (daily/weekly) risk overfitting to noise;
        less frequent (quarterly) may miss structural breaks.
    """
    refit_values = cfg.get("sensitivity", {}).get("refit_every_values", [5, 10, 21, 42, 63])
    use_fisher = bool(cfg.get("use_fisher_transform", True))

    print(f"\n[refit_sensitivity] Sweeping refit_every={refit_values} on {rep_base} vs {rep_other} w={rep_window}")
    y = build_target(returns, rep_base, rep_other, rep_window, 1, use_fisher)
    X = build_features(returns, rep_window, y, rep_base, rep_other, 1)
    y_aligned = y.loc[X.index]

    rows = []
    for rv in refit_values:
        try:
            _, metrics_df = fit_predict_walk_forward(
                X=X, y=y_aligned,
                min_train=int(cfg["min_train_size"]),
                refit_every=int(rv),
                random_state=int(cfg["random_state"]),
                use_xgb=bool(cfg.get("use_xgboost", True)),
                xgb_device=str(cfg.get("xgb_device", "cuda")),
            )
            for _, row in metrics_df.iterrows():
                rows.append({"refit_every": rv, "model": row["model"],
                             "RMSE": row["RMSE"], "R2": row["R2"]})
        except Exception as exc:
            warnings.warn(f"refit_sensitivity refit_every={rv} failed: {exc}")

    if not rows:
        return

    sens_df = pd.DataFrame(rows)
    out_csv = os.path.join(paths.results, "refit_sensitivity.csv")
    sens_df.to_csv(out_csv, index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    for model_name, grp in sens_df.groupby("model"):
        ax.plot(grp["refit_every"], grp["RMSE"], marker="o", label=model_name)
    ax.axvline(int(cfg.get("refit_every", 20)), linestyle="--", color="k",
               linewidth=1.2, label=f"Default ({cfg.get('refit_every', 20)} days)")
    ax.set_xlabel("refit_every (trading days)")
    ax.set_ylabel("OOS RMSE")
    ax.set_title(f"Refit frequency sensitivity — {rep_base} vs {rep_other} | w={rep_window}")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(paths.figures, "refit_sensitivity.png"), dpi=120)
    plt.close(fig)
    print(f"[refit_sensitivity] Saved → {out_csv}")


def test_cross_asset_performance_difference(
    paths: Paths,
    cfg: Dict,
    equity_assets: Optional[List[str]] = None,
    nonequity_assets: Optional[List[str]] = None,
) -> None:
    """DM test comparing forecast errors of equity vs non-equity pairs.

    Loads already-generated prediction CSVs (w=30), identifies the best model
    per pair by RMSE, averages errors across each group, then runs a
    Diebold-Mariano test for equal predictive accuracy between groups.
    Result saved to outputs/results/cross_asset_dm_test.csv.
    """
    if equity_assets is None:
        equity_assets = ["^GSPC", "^IXIC"]
    if nonequity_assets is None:
        nonequity_assets = ["GLD", "SLV", "UUP"]

    base = cfg.get("base_asset", "BTC-USD")
    windows = [int(w) for w in cfg.get("rolling_windows", [30])]
    target_space = "fisher_z" if bool(cfg.get("use_fisher_transform", True)) else "raw_corr"
    rep_window = 30 if 30 in windows else windows[len(windows) // 2]

    def _best_errors(asset: str) -> Optional[np.ndarray]:
        dep = f"corr_{base}_{asset}"
        pred_csv = os.path.join(paths.predictions, f"{dep}_w{rep_window}_{target_space}_predictions.csv")
        if not os.path.exists(pred_csv):
            return None
        df = pd.read_csv(pred_csv, index_col=0, parse_dates=True)
        if "y_true" not in df.columns:
            return None
        model_cols = [c for c in df.columns if c != "y_true"]
        best_rmse, best_err = np.inf, None
        for col in model_cols:
            mask = df[col].notna() & df["y_true"].notna()
            if mask.sum() < 50:
                continue
            rmse = float(np.sqrt(mean_squared_error(df.loc[mask, "y_true"], df.loc[mask, col])))
            if rmse < best_rmse:
                best_rmse = rmse
                best_err = (df["y_true"] - df[col]).dropna().values
        return best_err

    eq_errors  = [e for a in equity_assets    if (e := _best_errors(a)) is not None]
    neq_errors = [e for a in nonequity_assets if (e := _best_errors(a)) is not None]

    rows: List[Dict] = []
    if eq_errors and neq_errors:
        min_len = min(min(len(e) for e in eq_errors), min(len(e) for e in neq_errors))
        e_eq  = np.mean(np.vstack([e[-min_len:] for e in eq_errors]),  axis=0)
        e_neq = np.mean(np.vstack([e[-min_len:] for e in neq_errors]), axis=0)
        dm = diebold_mariano(e_eq, e_neq, h=1, nw_lag=int(cfg.get("dm_nw_lag", 0)))
        pv = dm.get("p_value")
        sig = ("***" if pv is not None and pv < 0.01
               else "**" if pv is not None and pv < 0.05
               else "*"  if pv is not None and pv < 0.10
               else "n.s.")
        rows.append({
            "group_a": "equity", "assets_a": str(equity_assets),
            "group_b": "non_equity", "assets_b": str(nonequity_assets),
            "n_pairs_a": len(eq_errors), "n_pairs_b": len(neq_errors),
            "window": rep_window, "significance": sig,
            **dm,
        })
        print(f"[cross_asset_dm] equity vs non-equity: DM={dm.get('DM_stat'):.3f} "
              f"p={dm.get('p_value'):.4f} {sig}")
    else:
        warnings.warn("cross_asset_dm: not enough prediction CSVs found. Run pipeline first.")

    out_csv = os.path.join(paths.results, "cross_asset_dm_test.csv")
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"[cross_asset_dm] Saved → {out_csv}")


def fit_predict_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int,
    refit_every: int,
    random_state: int,
    use_xgb: bool,
    xgb_device: str = "cuda",
    rf_n_jobs: int = -1,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    X_values = X.values
    idx = X.index
    y_values = y.loc[idx].values
    n_obs = len(idx)

    # Resolve effective XGB device once before the loop (avoids mid-loop failure)
    effective_device = _probe_xgb_device(xgb_device, random_state)

    model_specs: Dict[str, Optional[object]] = {
        "Naive_Last": None,
        "AR1":  LinearRegression(),
        "HAR":  None,   # Heterogeneous AutoRegressive — fitted explicitly below
        "ElasticNet": make_pipeline(StandardScaler(), ElasticNet(alpha=0.005, l1_ratio=0.5, random_state=random_state, max_iter=5000)),
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=0.5)),
        "RF": RandomForestRegressor(n_estimators=200, max_depth=10, min_samples_leaf=5, random_state=random_state, n_jobs=rf_n_jobs),
        "GBM": GradientBoostingRegressor(n_estimators=300, max_depth=4, learning_rate=0.02, subsample=0.8, min_samples_leaf=5, random_state=random_state),
    }

    if use_xgb and XGB_AVAILABLE:
        xgb_model = _make_xgb(effective_device, random_state)
        if xgb_model is not None:
            key = f"XGB_{'GPU' if effective_device == 'cuda' else 'CPU'}"
            model_specs[key] = xgb_model

    preds = {name: np.full(n_obs, np.nan, dtype=float) for name in model_specs}
    y_series = pd.Series(y_values, index=idx)
    fitted: Dict[str, object] = {}
    last_refit = -10**9

    for t in range(min_train, n_obs):
        train_idx = np.arange(0, t)

        if (t - last_refit) >= refit_every:
            last_refit = t
            X_train, y_train = X_values[train_idx], y_values[train_idx]

            ar_y = y_series.iloc[train_idx].values
            ar_x = y_series.iloc[train_idx].shift(1).values.reshape(-1, 1)
            valid = ~np.isnan(ar_x[:, 0])
            if int(valid.sum()) > 10:
                try:
                    model_specs["AR1"].fit(ar_x[valid], ar_y[valid])
                    fitted["AR1"] = model_specs["AR1"]
                except Exception:
                    fitted.pop("AR1", None)

            # HAR (Heterogeneous AutoRegressive) model:
            # ρ̂_{t+1} = α + β_d·ρ_t + β_w·avg(ρ_{t-4}..ρ_t) + β_m·avg(ρ_{t-21}..ρ_t)
            # Fitted by OLS; requires ≥23 training points with daily/weekly/monthly lags.
            if t >= 50:
                har_vals = y_series.iloc[:t].values
                har_feat, har_tgt = [], []
                for i in range(22, t):
                    lag1 = har_vals[i - 1]
                    lag_w = float(np.mean(har_vals[max(0, i - 5):i]))
                    lag_m = float(np.mean(har_vals[max(0, i - 22):i]))
                    tgt   = har_vals[i]
                    if np.isfinite(lag1) and np.isfinite(lag_w) and np.isfinite(lag_m) and np.isfinite(tgt):
                        har_feat.append([lag1, lag_w, lag_m])
                        har_tgt.append(tgt)
                if len(har_feat) >= 20:
                    try:
                        har_reg = LinearRegression()
                        har_reg.fit(har_feat, har_tgt)
                        fitted["HAR"] = har_reg
                    except Exception:
                        fitted.pop("HAR", None)

            # XGB: use last 20% of training window as early-stopping validation set.
            # A minimum of 100 validation points is required.
            xgb_key = next((k for k in model_specs if k.startswith("XGB_")), None)

            for name, model in list(model_specs.items()):
                if model is None or name in {"AR1", "HAR"}:
                    continue
                try:
                    if name == xgb_key and len(X_train) >= 500:
                        val_n = max(100, len(X_train) // 5)
                        X_tr, X_val = X_train[:-val_n], X_train[-val_n:]
                        y_tr, y_val = y_train[:-val_n], y_train[-val_n:]
                        model.set_params(early_stopping_rounds=30, eval_metric="rmse")
                        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
                    else:
                        model.fit(X_train, y_train)
                    fitted[name] = model
                except Exception as exc:
                    warnings.warn(f"Fit failed for {name} at t={t}: {exc}")
                    fitted.pop(name, None)

        if t > 0 and not np.isnan(y_values[t - 1]):
            preds["Naive_Last"][t] = y_values[t - 1]

        if "AR1" in fitted and not np.isnan(y_values[t - 1]):
            try:
                preds["AR1"][t] = fitted["AR1"].predict([[y_values[t - 1]]])[0]
            except Exception:
                pass

        # HAR prediction: use daily/weekly/monthly lags of the target series
        if "HAR" in fitted and t >= 23:
            lag1  = y_values[t - 1]
            lag_w = float(np.mean(y_values[max(0, t - 5):t]))
            lag_m = float(np.mean(y_values[max(0, t - 22):t]))
            if np.isfinite(lag1) and np.isfinite(lag_w) and np.isfinite(lag_m):
                try:
                    preds["HAR"][t] = fitted["HAR"].predict([[lag1, lag_w, lag_m]])[0]
                except Exception:
                    pass

        for name, model in fitted.items():
            if name in {"AR1", "HAR"}:
                continue
            try:
                preds[name][t] = model.predict(X_values[t : t + 1])[0]
            except Exception:
                pass

        # ── Adaptive ensemble ─────────────────────────────────────────────────
        # All non-naive models participate; weight = 1/RMSE over last 60 OOS steps.
        # Falls back to equal weights when history is too short (<10 valid pairs).
        _ADAPT_WIN = 60
        _all_cands = [n for n in {**fitted, **{"HAR": fitted.get("HAR")}}
                      if n not in {"Naive_Last"} and n in preds]
        _avail = [n for n in _all_cands if np.isfinite(preds[n][t])]
        if _avail:
            if "Ensemble" not in preds:
                preds["Ensemble"] = np.full(n_obs, np.nan, dtype=float)
            weights: Dict[str, float] = {}
            for n in _avail:
                start = max(min_train, t - _ADAPT_WIN)
                past_p = preds[n][start:t]
                past_y = y_values[start:t]
                ok = np.isfinite(past_p) & np.isfinite(past_y)
                if ok.sum() >= 10:
                    rmse_n = float(np.sqrt(np.mean((past_p[ok] - past_y[ok]) ** 2)))
                    weights[n] = 1.0 / (rmse_n + 1e-9)
                else:
                    weights[n] = 1.0
            total_w = sum(weights.values())
            if total_w > 0:
                preds["Ensemble"][t] = float(
                    sum(weights[n] * preds[n][t] for n in _avail) / total_w
                )

    pred_df = pd.DataFrame(preds, index=idx)
    metrics_df = compute_prediction_metrics(y.loc[idx], pred_df)
    return pred_df, metrics_df


def diebold_mariano(
    e_model: np.ndarray,
    e_bench: np.ndarray,
    h: int = 1,
    power: int = 2,
    nw_lag: int = 0,
) -> Dict:
    e_model = np.asarray(e_model, dtype=float)
    e_bench = np.asarray(e_bench, dtype=float)
    mask = np.isfinite(e_model) & np.isfinite(e_bench)
    e_model, e_bench = e_model[mask], e_bench[mask]
    sample_size = len(e_model)
    if sample_size < 30:
        return {"DM_stat": np.nan, "p_value": np.nan, "n": sample_size}

    d = (np.abs(e_bench) ** power) - (np.abs(e_model) ** power)
    d_mean = d.mean()
    variance = np.var(d, ddof=1)
    for lag in range(1, nw_lag + 1):
        cov = np.cov(d[lag:], d[:-lag], ddof=1)[0, 1]
        weight = 1.0 - lag / (nw_lag + 1.0)
        variance += 2 * weight * cov

    dm_stat = d_mean / math.sqrt(variance / sample_size) if variance > 0 else np.nan
    p_value = 2 * (1 - stats.t.cdf(abs(dm_stat), df=sample_size - 1)) if np.isfinite(dm_stat) else np.nan
    if np.isfinite(p_value):
        p_value = max(float(p_value), np.finfo(float).tiny)
    return {
        "DM_stat": float(dm_stat) if np.isfinite(dm_stat) else None,
        "p_value": float(p_value) if np.isfinite(p_value) else None,
        "n": sample_size,
    }


def plot_series(out_path: str, title: str, series_dict: Dict[str, pd.Series], figsize=(12, 5)) -> None:
    fig, ax = plt.subplots(figsize=figsize)
    for label, series in series_dict.items():
        ax.plot(series.index, series.values, label=label, linewidth=1)
    ax.set_title(title)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_forecast(
    y_true: pd.Series,
    pred_df: pd.DataFrame,
    out_path: str,
    title: str,
    top_models: Optional[List[str]] = None,
    top_k: int = 4,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(y_true.index, y_true.values, label="Actual", linewidth=1.8, color="black")
    cols = top_models if top_models else [c for c in pred_df.columns if pred_df[c].notna().sum() > 50][:top_k]
    colors = plt.cm.tab10.colors
    for i, column in enumerate(cols[:top_k]):
        ax.plot(pred_df.index, pred_df[column].values, label=column, alpha=0.85, linewidth=1, color=colors[i % len(colors)])
    ax.legend(ncol=2)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def describe_dataset(prices: pd.DataFrame, returns: pd.DataFrame, paths: Paths, cfg: Dict) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    for column in prices.columns:
        normed = prices[column] / prices[column].iloc[0]
        ax.plot(prices.index, normed, label=column, linewidth=1)
    ax.set_title("Normalized prices (Yahoo Finance, adjusted close)")
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(paths.figures, "dataset_prices.png"), dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 5))
    roll = returns.rolling(30).std()
    for column in roll.columns:
        ax.plot(roll.index, roll[column], label=column, linewidth=1)
    ax.set_title("30-day rolling volatility of log-returns")
    ax.legend(loc="best", ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(paths.figures, "dataset_volatility.png"), dpi=120)
    plt.close(fig)

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

    n_assets = len(returns.columns)
    n_cols = min(4, max(1, n_assets))
    n_rows = int(math.ceil(n_assets / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3.5 * n_rows))
    axes = np.atleast_1d(axes).reshape(n_rows, n_cols)
    for i, column in enumerate(returns.columns):
        ax = axes[i // n_cols, i % n_cols]
        ax.hist(returns[column].dropna(), bins=80, edgecolor="none", color="#2077b4", alpha=0.8)
        ax.set_title(column, fontsize=9)
        ax.set_xlabel("log-return")
    for j in range(n_assets, n_rows * n_cols):
        axes[j // n_cols, j % n_cols].axis("off")
    plt.suptitle("Return distributions", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(paths.figures, "dataset_return_dist.png"), dpi=120)
    plt.close()

    summary = {
        "n_days_prices": int(len(prices)),
        "n_days_returns": int(len(returns)),
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
        "tickers": list(prices.columns),
    }
    with open(os.path.join(paths.results, "dataset_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def write_metadata(paths: Paths, cfg: Dict) -> None:
    metadata = {"python": sys.version, "config": cfg}
    try:
        import importlib.metadata as md
        metadata["packages"] = {}
        for package in ["numpy", "pandas", "scikit-learn", "scipy", "yfinance", "xgboost", "arch"]:
            try:
                metadata["packages"][package] = md.version(package)
            except Exception:
                pass
    except Exception:
        pass

    with open(os.path.join(paths.results, "run_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


def metrics_to_latex(df: pd.DataFrame, out_tex: str, caption: str, label: str) -> None:
    if df.empty:
        return
    needed = ["dependency", "window", "target_space", "model", "MAE", "RMSE", "R2", "n_test"]
    out = df.copy()
    for column in needed:
        if column not in out.columns:
            out[column] = ""
    out = out[needed]
    for column in ["MAE", "RMSE", "R2"]:
        out[column] = out[column].apply(lambda value: f"{float(value):.4f}")
    out["n_test"] = out["n_test"].astype(str)

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\caption{" + caption + "}",
        r"\label{" + label + "}",
        r"\begin{tabular}{llllrrrr}",
        r"\toprule",
        r"Dependency & $w$ & Space & Model & MAE & RMSE & $R^2$ & $n$ \\",
        r"\midrule",
    ]
    for _, row in out.iterrows():
        lines.append(
            f"{row['dependency']} & {row['window']} & {row['target_space']} & {row['model']} & {row['MAE']} & {row['RMSE']} & {row['R2']} & {row['n_test']} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    with open(out_tex, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def dm_to_latex(df: pd.DataFrame, out_tex: str) -> None:
    if df.empty:
        return
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\caption{Diebold--Mariano tests for equal predictive accuracy}",
        r"\label{tab:dm_tests}",
        r"\begin{tabular}{llllrrl}",
        r"\toprule",
        r"Dependency & $w$ & Model & Benchmark & DM stat & $p$-value & Sign \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        dm_stat = row.get("DM_stat", "")
        p_value = row.get("p_value", "")
        try:
            dm_fmt = f"{float(dm_stat):.2f}"
            _pv = float(p_value)
            p_fmt = "<0.0001" if _pv < 0.0001 else f"{_pv:.4f}"
            sign = "***" if _pv < 0.01 else ("**" if _pv < 0.05 else ("*" if _pv < 0.1 else ""))
        except Exception:
            dm_fmt, p_fmt, sign = str(dm_stat), str(p_value), ""
        lines.append(
            f"{row.get('dependency', '')} & {row.get('window', '')} & {row.get('model', '')} & {row.get('benchmark', '')} & {dm_fmt} & {p_fmt} & {sign} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    with open(out_tex, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def run_experiment(
    returns: pd.DataFrame,
    paths: Paths,
    cfg: Dict,
    base: str,
    other: str,
    window: int,
    horizon: int,
    use_fisher: bool,
    rf_n_jobs: int = -1,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dependency_name = f"corr_{base}_{other}"
    target_space = "fisher_z" if use_fisher else "raw_corr"

    y = build_target(returns, base, other, window, horizon, use_fisher)
    X = build_features(returns, window, y, base, other, horizon)
    y_aligned = y.loc[X.index]

    pred_df, _ = fit_predict_walk_forward(
        X=X,
        y=y_aligned,
        min_train=int(cfg["min_train_size"]),
        refit_every=int(cfg["refit_every"]),
        random_state=int(cfg["random_state"]),
        use_xgb=bool(cfg.get("use_xgboost", True)),
        xgb_device=str(cfg.get("xgb_device", "cuda")),
        rf_n_jobs=rf_n_jobs,
    )

    out_df = pd.concat([y_aligned.rename("y_true"), pred_df], axis=1)

    if bool(cfg.get("use_dcc_garch", True)) and DCC_AVAILABLE:
        try:
            r1 = returns[base].loc[out_df.index]
            r2 = returns[other].loc[out_df.index]
            dcc_pred = dcc_garch_walk_forward_predict(
                r1,
                r2,
                min_train=int(cfg["min_train_size"]),
                refit_every=int(cfg["refit_every"]),
                horizon=horizon,
            )
            dcc_series = pd.Series(dcc_pred, index=out_df.index)
            out_df["DCC_GARCH"] = fisher_z(dcc_series) if use_fisher else dcc_series
        except Exception as exc:
            warnings.warn(f"DCC failed for {dependency_name} w={window}: {exc}")

    model_preds = out_df.drop(columns=["y_true"])
    metrics_df = compute_prediction_metrics(out_df["y_true"], model_preds)

    pred_csv = os.path.join(paths.predictions, f"{dependency_name}_w{window}_{target_space}_predictions.csv")
    out_df.to_csv(pred_csv, encoding="utf-8")

    top_models = metrics_df["model"].head(4).tolist() if not metrics_df.empty else None
    fig_path = os.path.join(paths.figures, f"{dependency_name}_w{window}_{target_space}.png")
    plot_forecast(
        out_df["y_true"],
        model_preds,
        fig_path,
        title=f"Forecasting: {dependency_name} | h={horizon} | w={window} | {target_space}",
        top_models=top_models,
        top_k=4,
    )

    dm_rows = []
    if not metrics_df.empty:
        ml_models = [
            m for m in metrics_df["model"].tolist()
            if m not in {"Naive_Last", "AR1", "DCC_GARCH"} and m in out_df.columns
        ]
        for test_model in ml_models:
            e_model = (out_df["y_true"] - out_df[test_model]).values
            for benchmark in ["Naive_Last", "DCC_GARCH"]:
                if benchmark in out_df.columns:
                    e_bench = (out_df["y_true"] - out_df[benchmark]).values
                    dm = diebold_mariano(e_model, e_bench, h=horizon, nw_lag=int(cfg.get("dm_nw_lag", 0)))
                    dm_rows.append(
                        {
                            "dependency": dependency_name,
                            "window": window,
                            "space": target_space,
                            "model": test_model,
                            "benchmark": benchmark,
                            **dm,
                        }
                    )

    dm_df = pd.DataFrame(dm_rows)
    signal_metrics_df = pd.DataFrame()
    if other in cfg.get("assets", {}).get("traditional", []) and bool(cfg.get("enable_signal_layer", True)):
        _, signal_metrics_df = run_signal_experiment(
            returns=returns,
            paths=paths,
            cfg=cfg,
            base=base,
            other=other,
            window=window,
            dependency_name=dependency_name,
            out_df=out_df,
            dependency_metrics=metrics_df,
            rf_n_jobs=rf_n_jobs,
        )

    if not metrics_df.empty:
        metrics_df.insert(0, "target_space", target_space)
        metrics_df.insert(0, "window", window)
        metrics_df.insert(0, "dependency", dependency_name)

    return out_df, metrics_df, dm_df, signal_metrics_df


def run_pipeline(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    paths = build_paths(cfg["base_dir"])
    ensure_dirs(paths)

    tickers = cfg["assets"]["crypto"] + cfg["assets"]["traditional"]
    prices = fetch_prices(paths, tickers, cfg["start_date"], cfg.get("end_date"))
    returns = compute_returns(paths, prices)

    describe_dataset(prices, returns, paths, cfg)
    write_metadata(paths, cfg)

    # ── Data quality report ──────────────────────────────────────────────────
    # Full diagnostics are saved in outputs/quality/; key figures and the
    # LaTeX table are also copied to outputs/figures/ and outputs/tables/ so
    # the thesis chapters can reference them directly.
    try:
        try:
            from thesis_app.data_quality import run_data_quality_report
        except ImportError:
            from data_quality import run_data_quality_report
        _dq_dir = os.path.join(paths.outputs, "quality")
        run_data_quality_report(prices, output_dir=_dq_dir)
        print(f"Data quality report saved → {_dq_dir}")

        # Export key artefacts to canonical output directories
        for _fig_name in ["fig_missing_heatmap.png", "fig_price_coverage.png", "fig_return_outliers.png"]:
            _src = os.path.join(_dq_dir, _fig_name)
            if os.path.exists(_src):
                shutil.copy2(_src, os.path.join(paths.figures, _fig_name))
        _tex_src = os.path.join(_dq_dir, "data_quality_table.tex")
        if os.path.exists(_tex_src):
            shutil.copy2(_tex_src, os.path.join(paths.tables, "data_quality_table.tex"))
        print(f"Data quality figures/table copied → {paths.figures} / {paths.tables}")
    except Exception as _dq_exc:
        warnings.warn(f"Data quality report skipped: {_dq_exc}")

    base = cfg.get("base_asset", "BTC-USD")
    others = cfg["assets"]["traditional"] + cfg.get("extra_assets", [])
    others = list(dict.fromkeys([other for other in others if other != base]))
    horizon = int(cfg.get("forecast_horizon", 1))
    windows = [int(window) for window in cfg.get("rolling_windows", [30])]
    use_fisher = bool(cfg.get("use_fisher_transform", True))

    all_metrics = []
    all_dm = []
    all_signal_metrics = []

    valid_others = [o for o in others if o in returns.columns]
    skipped = [o for o in others if o not in returns.columns]
    for o in skipped:
        print(f"Skip {o}: not in returns data.")

    # ── Sensitivity plots (fast, serial — all windows per pair together) ─────
    for other in valid_others:
        sensitivity = {f"w={window}": rolling_corr(returns[base], returns[other], window).dropna() for window in windows}
        plot_series(
            os.path.join(paths.figures, f"sensitivity_{base}_{other}.png"),
            f"Rolling correlation sensitivity: {base} vs {other}",
            sensitivity,
        )

    # ── Experiments (optionally parallel) ────────────────────────────────────
    # n_workers=1 → fully serial (safe, default).
    # Set n_parallel_workers in config.yaml to use multiple threads.
    # ThreadPoolExecutor is used (not ProcessPoolExecutor) because sklearn and
    # numpy release the GIL, giving real concurrency without pickling overhead.
    n_workers = int(cfg.get("n_parallel_workers", 1))
    if n_workers < 1:
        n_workers = max(1, multiprocessing.cpu_count() // 2)

    # Scale RF n_jobs to avoid CPU over-subscription when experiments run in parallel.
    # Serial mode: n_jobs=-1 (RF uses all cores for one experiment at a time).
    # Parallel mode: divide cores evenly among concurrent experiments.
    rf_n_jobs = max(1, multiprocessing.cpu_count() // n_workers) if n_workers > 1 else -1

    experiment_tasks = [
        (other, window)
        for other in valid_others
        for window in windows
    ]

    def _run_one_experiment(args):
        _other, _window = args
        print(f"\n> {base} vs {_other} | w={_window} | fisher={use_fisher}")
        try:
            _, m_df, d_df, s_df = run_experiment(
                returns=returns, paths=paths, cfg=cfg,
                base=base, other=_other, window=_window,
                horizon=horizon, use_fisher=use_fisher,
                rf_n_jobs=rf_n_jobs,
            )
            if not m_df.empty:
                best_row = m_df.iloc[0]
                print(f"  [{_other} w={_window}] Best: {best_row['model']} RMSE={best_row['RMSE']:.4f} R²={best_row['R2']:.3f}")
            if not s_df.empty:
                best_sig = s_df.iloc[0]
                print(f"  [{_other} w={_window}] Signal: {best_sig['signal_model']} F1={best_sig['F1Down']:.3f} BalAcc={best_sig['BalancedAccuracy']:.3f}")
            return m_df, d_df, s_df
        except Exception as exc:
            warnings.warn(f"Experiment failed for {base} vs {_other} w={_window}: {exc}")
            traceback.print_exc()
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    if n_workers == 1:
        # Serial path — simpler and always safe
        for task in experiment_tasks:
            m_df, d_df, s_df = _run_one_experiment(task)
            if not m_df.empty:
                all_metrics.append(m_df)
            if not d_df.empty:
                all_dm.append(d_df)
            if not s_df.empty:
                all_signal_metrics.append(s_df)
    else:
        print(f"\n[pipeline] Running {len(experiment_tasks)} experiments with {n_workers} parallel workers…")
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            future_map = {executor.submit(_run_one_experiment, task): task for task in experiment_tasks}
            for future in as_completed(future_map):
                m_df, d_df, s_df = future.result()
                if not m_df.empty:
                    all_metrics.append(m_df)
                if not d_df.empty:
                    all_dm.append(d_df)
                if not s_df.empty:
                    all_signal_metrics.append(s_df)

    if all_metrics:
        metrics_all = pd.concat(all_metrics).reset_index(drop=True)
        metrics_path = os.path.join(paths.results, "metrics.csv")
        metrics_all.to_csv(metrics_path, index=False)
        print(f"\nSaved metrics -> {metrics_path}")

        metrics_tex = os.path.join(paths.tables, "metrics_table.tex")
        metrics_to_latex(
            metrics_all.sort_values(["dependency", "window", "RMSE"]).head(60),
            metrics_tex,
            caption="Out-of-sample forecasting metrics.",
            label="tab:metrics",
        )
        print(f"Saved metrics LaTeX -> {metrics_tex}")

    if all_signal_metrics:
        signal_all = pd.concat(all_signal_metrics).reset_index(drop=True)
        signal_path = os.path.join(paths.results, "signal_metrics.csv")
        signal_all.to_csv(signal_path, index=False)
        print(f"Saved investor signal metrics -> {signal_path}")

        signal_tex = os.path.join(paths.tables, "signal_metrics.tex")
        signal_metrics_to_latex(
            signal_all.sort_values(["dependency", "window", "F1Down"], ascending=[True, True, False]).head(60),
            signal_tex,
        )
        print(f"Saved signal LaTeX -> {signal_tex}")

    if all_dm:
        dm_all = pd.concat(all_dm).reset_index(drop=True)
        dm_path = os.path.join(paths.results, "dm_tests.csv")
        dm_all.to_csv(dm_path, index=False)
        print(f"Saved DM tests -> {dm_path}")

        dm_tex = os.path.join(paths.tables, "dm_tests.tex")
        dm_to_latex(dm_all, dm_tex)
        print(f"Saved DM LaTeX -> {dm_tex}")

    # ── Regime analysis ──────────────────────────────────────────────────────
    # Uses a dedicated subdirectory: regime PNG figures AND CSV/TEX tables
    # are all placed in outputs/regimes/ to avoid mixing file types in
    # outputs/figures/ or outputs/tables/.
    try:
        try:
            from thesis_app.regime_analysis import run_regime_analysis
        except ImportError:
            from regime_analysis import run_regime_analysis
        regime_others = list(dict.fromkeys(
            [o for o in (cfg["assets"]["traditional"] + cfg.get("extra_assets", [])) if o != base]
        ))
        _regime_dir = os.path.join(paths.outputs, "regimes")
        run_regime_analysis(
            prices=prices,
            base=base,
            others=[o for o in regime_others if o in returns.columns],
            windows=windows,
            output_dir=_regime_dir,
        )
        print(f"Regime analysis saved → {_regime_dir}")
    except Exception as _ra_exc:
        warnings.warn(f"Regime analysis skipped: {_ra_exc}")

    # ── Bootstrap confidence intervals ───────────────────────────────────────
    # Re-reads prediction CSVs to compute bootstrap 95% CIs for RMSE and R2.
    # This is done post-hoc so the main walk-forward loop stays fast.
    try:
        n_bootstrap = int(cfg.get("bootstrap", {}).get("n_samples", 1000))
        target_space = "fisher_z" if use_fisher else "raw_corr"
        ci_rows = []
        for other in others:
            if other not in returns.columns:
                continue
            for window in windows:
                dep = f"corr_{base}_{other}"
                pred_csv = os.path.join(paths.predictions, f"{dep}_w{window}_{target_space}_predictions.csv")
                if not os.path.exists(pred_csv):
                    continue
                df_p = pd.read_csv(pred_csv, index_col=0, parse_dates=True)
                if "y_true" not in df_p.columns:
                    continue
                model_preds = df_p.drop(columns=["y_true"])
                ci_df = compute_metrics_with_ci(df_p["y_true"], model_preds,
                                                n_bootstrap=n_bootstrap,
                                                random_state=int(cfg.get("random_state", 42)))
                if not ci_df.empty:
                    ci_df.insert(0, "window", window)
                    ci_df.insert(0, "dependency", dep)
                    ci_rows.append(ci_df)
        if ci_rows:
            ci_all = pd.concat(ci_rows).reset_index(drop=True)
            ci_path = os.path.join(paths.results, "metrics_with_ci.csv")
            ci_all.to_csv(ci_path, index=False)
            print(f"Bootstrap CI metrics saved → {ci_path}")
    except Exception as _ci_exc:
        warnings.warn(f"Bootstrap CI computation skipped: {_ci_exc}")

    # ── Cross-asset DM test ───────────────────────────────────────────────────
    try:
        test_cross_asset_performance_difference(paths, cfg)
    except Exception as _ca_exc:
        warnings.warn(f"Cross-asset DM test skipped: {_ca_exc}")

    # ── Refit frequency sensitivity ───────────────────────────────────────────
    # Runs only on the representative pair (BTC vs ^GSPC, w=30) to limit runtime.
    try:
        if base in returns.columns and "^GSPC" in returns.columns:
            refit_sensitivity_analysis(returns, paths, cfg,
                                       rep_base=base, rep_other="^GSPC", rep_window=30)
    except Exception as _rs_exc:
        warnings.warn(f"Refit sensitivity analysis skipped: {_rs_exc}")

    print("\nPipeline complete.")
    if bool(cfg.get("use_dcc_garch", True)) and not DCC_AVAILABLE:
        print("Warning: DCC-GARCH was requested but could not be imported. Install 'arch' and check thesis_app/dcc_walk.py.")
