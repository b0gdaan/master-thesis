"""
Train, optimise, and persist the investor signal classifier.

Usage:
    python train_signal_model.py               # train for all key pairs
    python train_signal_model.py --pair GSPC   # train only for ^GSPC w=30

Outputs
-------
outputs/models/
    signal_logit_<pair>_w<window>.joblib    — full production model (all features)
    signal_web_<pair>_w<window>.joblib      — slim 5-feature model for browser demo
    model_metadata.json                     — metrics, coefficients, feature names

Updates
-------
docs/index.html — AR1 + Logit coefficients refreshed in the JS demo block
"""
import argparse
import json
import os
import sys
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

# ── project imports ────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from thesis_app.pipeline import (
    build_features,
    build_target,
    compute_returns,
    fetch_prices,
    fisher_z,
    build_paths,
    fit_predict_walk_forward,
)
from thesis_app.signal_layer import (
    build_signal_features,
    fit_predict_signal_walk_forward,
    compute_signal_metrics,
)

# ── constants ──────────────────────────────────────────────────────────────
WINDOW       = 30
BASE         = "BTC-USD"
TARGETS      = {"GSPC": "^GSPC", "IXIC": "^IXIC", "GLD": "GLD"}
ALL_TICKERS  = ["BTC-USD", "ETH-USD", "^GSPC", "^IXIC", "GLD", "SLV", "UUP"]
MIN_TRAIN    = 800
REFIT_EVERY  = 20
RANDOM_STATE = 42
STRESS_SIGMA = 0.75
THRESHOLD    = 0.55

# Web demo uses exactly these 5 features (derived from the 4 slider inputs):
#   z_now      = fisherZ(rho)           ~ dep_pred
#   |ret|      = |daily_return|         ~ btcusd_ret_lag1 absolute
#   vol_norm   = vol / 0.55             ~ btcusd_vol_20
#   |mom|      = |5d_momentum|          ~ btcusd_mom_5 absolute
#   dep_change = dep_pred_change_1      ~ dep_pred_change_1
WEB_FEATURES = [
    "dep_pred",
    "btcusd_ret_abs",
    "btcusd_vol_20_norm",
    "btcusd_mom_5_abs",
    "dep_pred_change_1",
]


# ── helpers ────────────────────────────────────────────────────────────────

def load_data(paths) -> tuple:
    """Return (prices, returns) DataFrames."""
    import yaml
    with open(os.path.join(ROOT, "config.yaml")) as fh:
        cfg = yaml.safe_load(fh)

    prices  = fetch_prices(paths, ALL_TICKERS,
                           cfg["start_date"], cfg.get("end_date"))
    returns = compute_returns(paths, prices)
    return prices, returns


def get_ar1_coefficients(returns: pd.DataFrame, other: str,
                          window: int = WINDOW,
                          min_train: int = MIN_TRAIN) -> dict:
    """Fit AR1 on the full historical sample and return (mu, phi)."""
    dep_name = f"corr_{BASE}_{other}"
    rc = returns[BASE].rolling(window).corr(returns[other])
    target = fisher_z(rc).dropna()

    X = target.shift(1).rename("lag1")
    df = pd.concat([target.rename("y"), X], axis=1).dropna()
    df = df.iloc[min_train:]          # exclude burn-in used for walk-forward

    if len(df) < 50:
        return {"mu": 0.0, "phi": 1.0}

    from sklearn.linear_model import LinearRegression
    m = LinearRegression().fit(df[["lag1"]].values, df["y"].values)
    return {"mu": float(m.intercept_), "phi": float(m.coef_[0])}


def build_enhanced_features(signal_data: pd.DataFrame) -> pd.DataFrame:
    """
    Add extra engineered features to signal_data (already has base features).
    New columns:
        btcusd_ret_abs       abs daily return
        btcusd_vol_20_norm   vol / 0.55   (normalised to 'typical')
        btcusd_mom_5_abs     |5d momentum|
        dep_pred_pos         max(0, dep_pred)  – co-movement indicator
        dep_pred_neg         max(0,-dep_pred)  – diversifier indicator
        dep_x_vol            dep_pred_abs * btcusd_vol_20_norm
        ret_x_dep            btcusd_ret_abs * dep_pred_pos
    Returns a copy; original is not modified.
    """
    df = signal_data.copy()
    btc_col = [c for c in df.columns if "btcusd_ret_lag1" in c]
    vol_col  = [c for c in df.columns if "btcusd_vol_20"  in c]
    mom_col  = [c for c in df.columns if "btcusd_mom_5"   in c and "abs" not in c]

    if btc_col:
        df["btcusd_ret_abs"]     = df[btc_col[0]].abs()
    if vol_col:
        df["btcusd_vol_20_norm"] = df[vol_col[0]] / 0.55
    if mom_col:
        df["btcusd_mom_5_abs"]   = df[mom_col[0]].abs()

    df["dep_pred_pos"] = df["dep_pred"].clip(lower=0)
    df["dep_pred_neg"] = (-df["dep_pred"]).clip(lower=0)

    if "btcusd_vol_20_norm" in df.columns:
        df["dep_x_vol"] = df["dep_pred_abs"] * df["btcusd_vol_20_norm"]
    if "btcusd_ret_abs" in df.columns:
        df["ret_x_dep"] = df["btcusd_ret_abs"] * df["dep_pred_pos"]

    return df


def time_series_cv_logit(X: np.ndarray, y: np.ndarray,
                          n_splits: int = 5) -> float:
    """Return best C from TimeSeriesSplit CV (maximise AUC)."""
    C_grid = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
    tscv   = TimeSeriesSplit(n_splits=n_splits)
    scores = {}
    for C in C_grid:
        aucs = []
        for train_idx, val_idx in tscv.split(X):
            # Respect minimum train size
            if len(train_idx) < MIN_TRAIN:
                continue
            Xtr, ytr = X[train_idx], y[train_idx]
            Xva, yva = X[val_idx],   y[val_idx]
            if ytr.sum() < 20 or yva.sum() < 5:
                continue
            pipe = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=C, max_iter=3000,
                                   class_weight="balanced",
                                   random_state=RANDOM_STATE, solver="lbfgs"),
            )
            pipe.fit(Xtr, ytr)
            prob = pipe.predict_proba(Xva)[:, 1]
            if len(np.unique(yva)) > 1:
                aucs.append(roc_auc_score(yva, prob))
        scores[C] = float(np.mean(aucs)) if aucs else 0.0

    best_C = max(scores, key=scores.get)
    print(f"  CV AUC by C: {', '.join(f'{c:.3f}->{v:.4f}' for c,v in scores.items())}")
    print(f"  Best C = {best_C}  (CV AUC = {scores[best_C]:.4f})")
    return best_C


def train_full_model(X: np.ndarray, y: np.ndarray,
                     best_C: float) -> CalibratedClassifierCV:
    """Train calibrated logistic regression on full historical data."""
    base = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_C, max_iter=3000,
                           class_weight="balanced",
                           random_state=RANDOM_STATE, solver="lbfgs"),
    )
    # Platt calibration with time-series folds
    cal = CalibratedClassifierCV(
        base, cv=TimeSeriesSplit(n_splits=5), method="sigmoid"
    )
    cal.fit(X, y)
    return cal


def walk_forward_evaluate(signal_data: pd.DataFrame,
                           feature_cols: list,
                           best_C: float) -> dict:
    """OOS walk-forward evaluation for the chosen feature set and C."""
    X   = signal_data[feature_cols].values
    y   = signal_data["target_down"].astype(int).values
    n   = len(X)

    probs = np.full(n, np.nan)
    fitted_model = None
    last_refit   = -10**9

    for t in range(MIN_TRAIN, n):
        if (t - last_refit) >= REFIT_EVERY:
            last_refit = t
            Xtr, ytr = X[:t], y[:t]
            if ytr.sum() < 20 or (len(ytr) - ytr.sum()) < 20:
                continue
            pipe = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=best_C, max_iter=3000,
                                   class_weight="balanced",
                                   random_state=RANDOM_STATE, solver="lbfgs"),
            )
            try:
                pipe.fit(Xtr, ytr)
                fitted_model = pipe
            except Exception:
                pass
        if fitted_model is not None:
            probs[t] = fitted_model.predict_proba(X[t:t+1])[0, 1]

    oos_mask = ~np.isnan(probs) & (y == y)
    yp = probs[oos_mask]
    yt = y[oos_mask]
    sig = (yp >= THRESHOLD).astype(int)
    return {
        "BalancedAccuracy": round(balanced_accuracy_score(yt, sig), 4),
        "F1_down":          round(f1_score(yt, sig, zero_division=0), 4),
        "AUC":              round(roc_auc_score(yt, yp), 4) if yt.sum() > 0 else None,
        "n_test":           int(oos_mask.sum()),
        "n_pos":            int(yt.sum()),
        "best_C":           best_C,
    }


def extract_web_coefficients(full_model: CalibratedClassifierCV,
                              feature_cols: list,
                              web_features: list,
                              X_train: np.ndarray,
                              y_train: np.ndarray) -> dict:
    """
    Train a simple 5-feature Logit (for web demo) and extract raw coefficients.
    The web model uses WEB_FEATURES after StandardScaler transformation.
    We return the *unscaled* coefficients so the JS can use raw slider values.
    """
    web_idx = [feature_cols.index(f) for f in web_features if f in feature_cols]
    if not web_idx:
        return {}

    Xw   = X_train[:, web_idx]
    scaler = StandardScaler()
    Xw_sc = scaler.fit_transform(Xw)

    lr = LogisticRegression(C=0.1, max_iter=3000,
                             class_weight="balanced",
                             random_state=RANDOM_STATE, solver="lbfgs")
    lr.fit(Xw_sc, y_train)

    # Convert to unscaled space:  b_raw = b_scaled / std,  intercept -= sum(b_raw * mean)
    b_scaled = lr.coef_[0]          # shape (n_web_features,)
    b_raw    = b_scaled / scaler.scale_
    intercept_raw = float(lr.intercept_[0]) - float(np.dot(b_raw, scaler.mean_))

    prob_train = lr.predict_proba(Xw_sc)[:, 1]
    auc_web = roc_auc_score(y_train, prob_train) if y_train.sum() > 0 else None

    return {
        "intercept":  round(intercept_raw, 5),
        "coefficients": {wf: round(float(b), 5)
                         for wf, b in zip(web_features, b_raw)
                         if wf in feature_cols},
        "scaler_mean":  dict(zip(web_features,
                                  [round(float(m), 6) for m in scaler.mean_])),
        "scaler_std":   dict(zip(web_features,
                                  [round(float(s), 6) for s in scaler.scale_])),
        "in_sample_auc": round(auc_web, 4) if auc_web else None,
    }


def update_website(ar1: dict, web_coef: dict, metrics_full: dict,
                   metrics_web: dict, pair_key: str) -> None:
    """Patch AR1 + LR_W constants in docs/index.html."""
    html_path = os.path.join(ROOT, "docs", "index.html")
    if not os.path.exists(html_path):
        print(f"  [skip] {html_path} not found")
        return

    with open(html_path, encoding="utf-8") as fh:
        src = fh.read()

    # Build JS constant block
    mu  = ar1["mu"]
    phi = ar1["phi"]
    ic  = web_coef["intercept"]
    co  = web_coef["coefficients"]

    # Map web features to LR_W order:
    #   LR_W[0] = intercept
    #   LR_W[1] = dep_pred         (z_now input)
    #   LR_W[2] = btcusd_ret_abs
    #   LR_W[3] = btcusd_vol_20_norm
    #   LR_W[4] = btcusd_mom_5_abs
    #   LR_W[5] = dep_pred_change_1
    lrw = [
        ic,
        co.get("dep_pred",         0.0),
        co.get("btcusd_ret_abs",   0.0),
        co.get("btcusd_vol_20_norm", 0.0),
        co.get("btcusd_mom_5_abs", 0.0),
        co.get("dep_pred_change_1",0.0),
    ]
    lrw_str = "[" + ", ".join(f"{v:.4f}" for v in lrw) + "]"

    f1_full  = metrics_full.get("F1_down",  "?")
    auc_full = metrics_full.get("AUC",      "?")
    rmse_ar1 = 0.0664  # from main results (AR1 BTC-GSPC w=30)
    r2_ar1   = 0.9420

    new_block = (
        f"const AR1_INTERCEPT = {mu:.4f};\n"
        f"const AR1_BETA      = {phi:.4f};\n"
        f"\nconst LR_W = {lrw_str};  // intercept, dep_pred, |ret|, vol_norm, |mom|, dep_change"
    )

    import re
    # Replace existing block
    pattern = (
        r"const AR1_INTERCEPT\s*=\s*[^;]+;\s*\n"
        r"const AR1_BETA\s*=\s*[^;]+;\s*\n"
        r"\s*\nconst LR_W\s*=\s*\[[^\]]+\][^;]*;"
    )
    updated = re.sub(pattern, new_block, src)

    if updated == src:
        print("  [warn] Regex did not match — patching manually")
        # Fallback: replace each constant individually
        updated = re.sub(r"const AR1_INTERCEPT\s*=\s*[^;]+;",
                         f"const AR1_INTERCEPT = {mu:.4f};", src)
        updated = re.sub(r"const AR1_BETA\s*=\s*[^;]+;",
                         f"const AR1_BETA      = {phi:.4f};", updated)
        updated = re.sub(r"const LR_W\s*=\s*\[[^\]]+\][^;]*;",
                         f"const LR_W = {lrw_str};  // intercept, dep_pred, |ret|, vol_norm, |mom|, dep_change",
                         updated)

    # Update pill labels
    rmse_str = f"RMSE={rmse_ar1:.4f}"
    r2_str   = f"R²={r2_ar1:.2f}"
    f1_str   = f"F1={f1_full:.3f}"
    auc_str  = f"AUC={auc_full:.3f}"

    updated = re.sub(
        r"AR1\s*·\s*RMSE=[\d.]+\s*·\s*R²=[\d.]+",
        f"AR1 · {rmse_str} · {r2_str}", updated)
    updated = re.sub(
        r"Logit\s*·\s*F1=[\d.]+\s*·\s*AUC=[\d.]+",
        f"Logit · {f1_str} · {auc_str}", updated)

    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print(f"  Updated docs/index.html  AR1(mu={mu:.4f}, phi={phi:.4f})  "
          f"LR_W={lrw_str}")


# ── main ───────────────────────────────────────────────────────────────────

def run(pair_key: str = "GSPC") -> None:
    other = TARGETS.get(pair_key, pair_key)
    dep_name = f"corr_{BASE}_{other}"
    print(f"\n{'='*60}")
    print(f"Training signal model: {BASE} vs {other}  w={WINDOW}")
    print(f"{'='*60}")

    # 1. Load data
    paths = build_paths(ROOT)
    os.makedirs(os.path.join(ROOT, "outputs", "models"), exist_ok=True)
    prices, returns = load_data(paths)

    # 2. Get AR1 walk-forward predictions (already computed in main pipeline)
    pred_path = os.path.join(
        ROOT, "outputs", "predictions",
        f"corr_{BASE}_{other}_w{WINDOW}_fisher_z_predictions.csv"
    )
    if not os.path.exists(pred_path):
        print(f"  ERROR: {pred_path} not found — run main.py first")
        return
    preds = pd.read_csv(pred_path, index_col=0, parse_dates=True)

    # 3. Build full feature matrix
    print("  Building features…")
    signal_data_raw = build_signal_features(
        returns=returns,
        dependency_prediction=preds["AR1"],
        base=BASE,
        other=other,
        horizon=1,
        target_mode="stress",
        stress_sigma=STRESS_SIGMA,
    )
    signal_data = build_enhanced_features(signal_data_raw)
    signal_data  = signal_data.dropna()

    exclude = {"next_return", "target_down"}
    feature_cols = [c for c in signal_data.columns if c not in exclude]
    X_all = signal_data[feature_cols].values
    y_all = signal_data["target_down"].astype(int).values

    print(f"  Feature matrix: {X_all.shape}  positives: {y_all.sum()} / {len(y_all)}")

    # 4. Time-series CV to pick best C
    print("  Time-series CV for C…")
    X_train = X_all[:int(len(X_all) * 0.80)]
    y_train = y_all[:int(len(y_all) * 0.80)]
    best_C = time_series_cv_logit(X_train, y_train)

    # 5. Walk-forward OOS evaluation with best C and full feature set
    print("  Walk-forward OOS evaluation (full features)…")
    metrics_full = walk_forward_evaluate(signal_data, feature_cols, best_C)
    print(f"  Full model  BalAcc={metrics_full['BalancedAccuracy']}  "
          f"F1={metrics_full['F1_down']}  AUC={metrics_full['AUC']}")

    # 6. Walk-forward OOS evaluation for web features only
    web_feats_present = [f for f in WEB_FEATURES if f in signal_data.columns]
    print(f"  Walk-forward OOS evaluation (web features: {web_feats_present})…")
    metrics_web = walk_forward_evaluate(signal_data, web_feats_present, 0.10)
    print(f"  Web model   BalAcc={metrics_web['BalancedAccuracy']}  "
          f"F1={metrics_web['F1_down']}  AUC={metrics_web['AUC']}")

    # 7. Train final production model on full data
    print("  Training final calibrated model on full data…")
    full_model = train_full_model(X_all, y_all, best_C)

    # 8. Extract web demo coefficients
    print("  Extracting web demo coefficients…")
    web_coef = extract_web_coefficients(
        full_model, feature_cols, web_feats_present, X_all, y_all)
    print(f"  Web coeff: {web_coef['coefficients']}")

    # 9. Save models
    models_dir = os.path.join(ROOT, "outputs", "models")
    full_path = os.path.join(models_dir, f"signal_logit_{pair_key}_w{WINDOW}.joblib")
    web_path  = os.path.join(models_dir, f"signal_web_{pair_key}_w{WINDOW}.joblib")

    # Save full model metadata alongside it
    full_meta = {
        "model_type":    "CalibratedLogisticRegression",
        "pair":          f"{BASE} vs {other}",
        "window":        WINDOW,
        "features":      feature_cols,
        "best_C":        best_C,
        "metrics_oos":   metrics_full,
        "web_features":  web_feats_present,
        "web_metrics_oos": metrics_web,
        "web_coefficients": web_coef,
        "trained_on":    str(pd.Timestamp.now().date()),
        "n_obs":         len(X_all),
    }

    # Save slim web model
    web_feats_idx = [feature_cols.index(f) for f in web_feats_present]
    web_pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.10, max_iter=3000,
                            class_weight="balanced",
                            random_state=RANDOM_STATE, solver="lbfgs"),
    )
    web_pipe.fit(X_all[:, web_feats_idx], y_all)

    joblib.dump(full_model, full_path, compress=3)
    joblib.dump(web_pipe,   web_path,  compress=3)
    print(f"  Saved: {full_path}")
    print(f"  Saved: {web_path}")

    meta_path = os.path.join(models_dir, "model_metadata.json")
    # Merge with existing metadata
    existing = {}
    if os.path.exists(meta_path):
        with open(meta_path) as fh:
            existing = json.load(fh)
    existing[f"{pair_key}_w{WINDOW}"] = full_meta
    with open(meta_path, "w") as fh:
        json.dump(existing, fh, indent=2)
    print(f"  Saved: {meta_path}")

    # 10. AR1 coefficients (fit on full sample)
    ar1_coef = get_ar1_coefficients(returns, other)
    print(f"  AR1:  mu={ar1_coef['mu']:.4f}  phi={ar1_coef['phi']:.4f}")

    # 11. Update website demo
    print("  Updating docs/index.html…")
    update_website(ar1_coef, web_coef, metrics_full, metrics_web, pair_key)

    print(f"\n{'='*60}")
    print(f"Done!  Full model: {metrics_full}")
    print(f"       Web  model: {metrics_web}")
    print(f"{'='*60}\n")

    return full_meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and save signal classifier")
    parser.add_argument("--pair", default="GSPC",
                        choices=list(TARGETS.keys()),
                        help="Asset pair key (default: GSPC)")
    args = parser.parse_args()
    run(args.pair)
