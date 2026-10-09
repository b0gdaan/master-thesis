"""
Investor-facing signal layer built on top of dependency forecasts.
"""
import os
import warnings
from typing import Dict, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_signal_target(
    returns: pd.DataFrame,
    asset: str,
    horizon: int,
    mode: str = "stress",
    stress_sigma: float = 0.75,
) -> pd.DataFrame:
    next_return = returns[asset].shift(-horizon)
    trailing_vol = returns[asset].rolling(20).std().shift(1)
    if mode == "direction":
        target_event = next_return < 0
    else:
        target_event = next_return < (-stress_sigma * trailing_vol)
    return pd.DataFrame(
        {
            "next_return": next_return,
            "target_down": target_event.astype(float),
        }
    ).dropna()


def rolling_corr(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    return a.rolling(window).corr(b)


def build_signal_features(
    returns: pd.DataFrame,
    dependency_prediction: pd.Series,
    base: str,
    other: str,
    horizon: int,
    target_mode: str = "stress",
    stress_sigma: float = 0.75,
    short_corr_window: int = 14,
    vol_window: int = 20,
) -> pd.DataFrame:
    """
    Build the feature matrix for the investor signal layer.

    Feature groups
    --------------
    dep_*    – dependency forecast levels, lags, and changes
    base_*   – lagged returns, rolling volatility, momentum of the base crypto asset
    eth_*    – optional Ethereum features (skipped if ETH-USD not in returns)
    corr_*   – short-window rolling correlation between base and other asset
    spread_* – absolute return spread between base and other

    Parameters
    ----------
    short_corr_window : rolling window for cross-asset correlation features (days)
    vol_window        : rolling window for base-asset volatility features (days)
    """
    idx = dependency_prediction.index
    features = pd.DataFrame(index=idx)

    # Use a sanitized ticker string as the column prefix (e.g. "BTC-USD" → "btcusd")
    base_key = base.replace("-", "").replace("^", "").replace(".", "").lower()
    base_ret = returns[base]

    # Dependency forecast features
    features["dep_pred"] = dependency_prediction
    features["dep_pred_lag1"] = dependency_prediction.shift(1)
    features["dep_pred_change_1"] = dependency_prediction.diff(1)
    features["dep_pred_change_5"] = dependency_prediction.diff(5)
    features["dep_pred_abs"] = dependency_prediction.abs()

    # Base crypto return lags
    for lag in [1, 2, 5, 10]:
        features[f"{base_key}_ret_lag{lag}"] = base_ret.shift(lag).reindex(idx)

    # Base crypto volatility and momentum
    features[f"{base_key}_vol_5"]          = base_ret.rolling(5).std().reindex(idx)
    features[f"{base_key}_vol_{vol_window}"] = base_ret.rolling(vol_window).std().reindex(idx)
    features[f"{base_key}_mom_5"]           = base_ret.rolling(5).sum().reindex(idx)
    features[f"{base_key}_mom_{vol_window}"] = base_ret.rolling(vol_window).sum().reindex(idx)
    features[f"{base_key}_down_streak_5"]   = (base_ret < 0).astype(int).rolling(5).sum().reindex(idx)

    # Optional Ethereum cross-features
    if "ETH-USD" in returns.columns and "ETH-USD" != base:
        eth = returns["ETH-USD"]
        features["eth_ret_lag1"]     = eth.shift(1).reindex(idx)
        features["eth_ret_lag5"]     = eth.shift(5).reindex(idx)
        features["base_eth_spread_1"] = (base_ret.shift(1) - eth.shift(1)).reindex(idx)
        features["base_eth_corr"]     = rolling_corr(base_ret, eth, short_corr_window).shift(1).reindex(idx)

    # Cross-asset correlation and spread features
    features["base_other_corr"]     = rolling_corr(base_ret, returns[other], short_corr_window).shift(1).reindex(idx)
    features["base_other_spread_5"] = (base_ret - returns[other]).abs().rolling(5).mean().shift(1).reindex(idx)

    signal_target = build_signal_target(returns, other, horizon, mode=target_mode, stress_sigma=stress_sigma)
    return features.join(signal_target, how="inner").dropna()


def fit_predict_signal_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int,
    refit_every: int,
    random_state: int,
) -> pd.DataFrame:
    X_values = X.values
    idx = X.index
    y_values = y.loc[idx].astype(int).values
    n_obs = len(idx)

    model_specs: Dict[str, object] = {
        "Logit": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_state)),
        "RF_Cls": RandomForestClassifier(n_estimators=300, max_depth=6, random_state=random_state, n_jobs=-1, class_weight="balanced_subsample"),
        "GBM_Cls": GradientBoostingClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, random_state=random_state),
    }

    prob_preds = {name: np.full(n_obs, np.nan, dtype=float) for name in model_specs}
    fitted: Dict[str, object] = {}
    last_refit = -10**9

    for t in range(min_train, n_obs):
        train_idx = np.arange(0, t)
        if (t - last_refit) >= refit_every:
            last_refit = t
            X_train, y_train = X_values[train_idx], y_values[train_idx]
            if len(np.unique(y_train)) < 2:
                continue
            for name, model in model_specs.items():
                try:
                    model.fit(X_train, y_train)
                    fitted[name] = model
                except Exception as exc:
                    warnings.warn(f"Signal fit failed for {name} at t={t}: {exc}")
                    fitted.pop(name, None)

        for name, model in fitted.items():
            try:
                prob_preds[name][t] = model.predict_proba(X_values[t : t + 1])[0, 1]
            except Exception:
                pass

    return pd.DataFrame(prob_preds, index=idx)


def compute_signal_metrics(
    y_true: pd.Series,
    next_returns: pd.Series,
    prob_df: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    rows = []
    for model_name in prob_df.columns:
        mask = prob_df[model_name].notna() & y_true.notna() & next_returns.notna()
        if int(mask.sum()) < 50:
            continue
        yt = y_true.loc[mask].astype(int)
        yp = prob_df.loc[mask, model_name].astype(float)
        signal = (yp >= threshold).astype(int)
        flagged_returns = next_returns.loc[mask][signal == 1]
        clear_returns = next_returns.loc[mask][signal == 0]
        rows.append(
            {
                "signal_model": model_name,
                "Accuracy": float(accuracy_score(yt, signal)),
                "BalancedAccuracy": float(balanced_accuracy_score(yt, signal)),
                "PrecisionDown": float(precision_score(yt, signal, zero_division=0)),
                "RecallDown": float(recall_score(yt, signal, zero_division=0)),
                "F1Down": float(f1_score(yt, signal, zero_division=0)),
                "AUC": float(roc_auc_score(yt, yp)) if yt.nunique() > 1 else np.nan,
                "ExitRate": float(signal.mean()),
                "AvgReturnFlagged": float(flagged_returns.mean()) if len(flagged_returns) else np.nan,
                "AvgReturnClear": float(clear_returns.mean()) if len(clear_returns) else np.nan,
                "n_test": int(mask.sum()),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["F1Down", "BalancedAccuracy"], ascending=[False, False]).reset_index(drop=True)


def plot_signal_probability(
    signal_df: pd.DataFrame,
    out_path: str,
    title: str,
    probability_column: str,
    threshold: float,
) -> None:
    plt.figure(figsize=(13, 5))
    plt.plot(signal_df.index, signal_df[probability_column], label=f"{probability_column} P(down)", color="#c23b22", linewidth=1.2)
    plt.plot(signal_df.index, signal_df["target_down"], label="Actual down-day", color="#1f4e79", alpha=0.5, linewidth=0.8)
    plt.axhline(threshold, linestyle="--", color="black", linewidth=1, label=f"Threshold={threshold:.2f}")
    plt.ylim(-0.05, 1.05)
    plt.legend(ncol=3)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def signal_metrics_to_latex(df: pd.DataFrame, out_tex: str) -> None:
    if df.empty:
        return
    cols = [
        "dependency",
        "window",
        "signal_target",
        "dependency_model",
        "signal_model",
        "BalancedAccuracy",
        "F1Down",
        "AUC",
        "ExitRate",
        "AvgReturnFlagged",
        "AvgReturnClear",
    ]
    out = df[cols].copy()
    for column in ["BalancedAccuracy", "F1Down", "AUC", "ExitRate", "AvgReturnFlagged", "AvgReturnClear"]:
        out[column] = out[column].apply(lambda value: f"{float(value):.4f}" if pd.notna(value) else "")

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\caption{Investor signal layer: down-market detection from crypto and dependency forecasts}",
        r"\label{tab:signal_metrics}",
        r"\begin{tabular}{lllllrrrrr}",
        r"\toprule",
        r"Dependency & $w$ & Target & Dep. model & Signal model & BalAcc & F1_down & AUC & ExitRate & Flagged/Clear \\",
        r"\midrule",
    ]
    for _, row in out.iterrows():
        flagged_clear = f"{row['AvgReturnFlagged']} / {row['AvgReturnClear']}"
        lines.append(
            f"{row['dependency']} & {row['window']} & {row['signal_target']} & {row['dependency_model']} & {row['signal_model']} & {row['BalancedAccuracy']} & {row['F1Down']} & {row['AUC']} & {row['ExitRate']} & {flagged_clear} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    with open(out_tex, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def run_signal_experiment(
    returns: pd.DataFrame,
    paths,
    cfg: Dict,
    base: str,
    other: str,
    window: int,
    dependency_name: str,
    out_df: pd.DataFrame,
    dependency_metrics: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    threshold = float(cfg.get("signal_probability_threshold", 0.55))
    dependency_model = dependency_metrics.iloc[0]["model"] if not dependency_metrics.empty else "Naive_Last"
    if dependency_model not in out_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    signal_data = build_signal_features(
        returns=returns,
        dependency_prediction=out_df[dependency_model],
        base=base,
        other=other,
        horizon=int(cfg.get("forecast_horizon", 1)),
        target_mode=str(cfg.get("signal_target_mode", "stress")),
        stress_sigma=float(cfg.get("signal_stress_sigma", 0.75)),
    )
    if signal_data.empty:
        return pd.DataFrame(), pd.DataFrame()

    X_signal = signal_data.drop(columns=["next_return", "target_down"])
    y_signal = signal_data["target_down"].astype(int)
    prob_df = fit_predict_signal_walk_forward(
        X=X_signal,
        y=y_signal,
        min_train=int(cfg.get("signal_min_train_size", cfg.get("min_train_size", 800))),
        refit_every=int(cfg.get("signal_refit_every", cfg.get("refit_every", 20))),
        random_state=int(cfg.get("random_state", 42)),
    )
    metrics_df = compute_signal_metrics(y_signal, signal_data["next_return"], prob_df, threshold)
    if metrics_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    best_signal_model = metrics_df.iloc[0]["signal_model"]
    signal_out = pd.concat([signal_data[["next_return", "target_down"]], prob_df], axis=1)
    signal_out["best_signal_flag"] = (signal_out[best_signal_model] >= threshold).astype(float)

    metrics_df.insert(0, "dependency_model", dependency_model)
    signal_label = f"{cfg.get("signal_target_mode", "stress")}_{other}"
    metrics_df.insert(0, "signal_target", signal_label)
    metrics_df.insert(0, "window", window)
    metrics_df.insert(0, "dependency", dependency_name)

    signal_csv = os.path.join(paths.predictions, f"signal_{dependency_name}_w{window}.csv")
    signal_out.to_csv(signal_csv, encoding="utf-8")

    fig_path = os.path.join(paths.figures, f"signal_{dependency_name}_w{window}.png")
    plot_signal_probability(
        signal_out,
        fig_path,
        title=f"Investor signal: {other} down-day risk from crypto + dependency forecast",
        probability_column=best_signal_model,
        threshold=threshold,
    )
    return signal_out, metrics_df
