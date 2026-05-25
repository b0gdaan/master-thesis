"""
Investor-facing signal layer built on top of dependency forecasts.
"""
import os
import threading
import warnings
from typing import Dict, List, Optional, Tuple

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
from sklearn.utils.class_weight import compute_sample_weight

# Locks for shared output files written by all parallel signal experiments.
_DIAG_FILE_LOCK = threading.Lock()
_SENS_FILE_LOCK = threading.Lock()


def build_signal_target(
    returns: pd.DataFrame,
    asset: str,
    horizon: int,
    mode: str = "stress",
    stress_sigma: float = 0.75,
) -> pd.DataFrame:
    """Build the binary stress-day target for a traditional asset.

    Stress day definition (mode='stress')
    --------------------------------------
    target_down_t = 1  iff  r_{t+h}  <  -stress_sigma * σ̂_t

    where
        r_{t+h}  = log-return of `asset` h days ahead (h = horizon)
        σ̂_t      = 20-day trailing volatility, lagged 1 day (no look-ahead)
        stress_sigma  = threshold in units of σ̂_t
                        (default 0.75; configurable via config.yaml `signal_stress_sigma`)

    Choosing stress_sigma = 0.75
        At σ=0.75 roughly 15–20 % of days qualify as stress events for the
        traditional assets in this study, providing enough positive-class samples
        for reliable classifier training while targeting economically meaningful
        down-moves (losses exceeding ¾ of one daily standard deviation).

        The value is read from config.yaml (`signal_stress_sigma`) so that
        sensitivity across [0.5, 0.75, 1.0, 1.5, 2.0] can be explored
        without code changes (see outputs/results/stress_threshold_sensitivity.csv).

    Alternative mode (mode='direction')
        target_down_t = 1  iff  r_{t+h} < 0  (any negative return).
        More balanced classes but noisier target.
    """
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
) -> pd.DataFrame:
    idx = dependency_prediction.index
    features = pd.DataFrame(index=idx)
    base_r = returns[base]
    base_key = base.replace("-", "").replace("^", "").lower()

    features["dep_pred"] = dependency_prediction
    features["dep_pred_lag1"] = dependency_prediction.shift(1)
    features["dep_pred_change_1"] = dependency_prediction.diff(1)
    features["dep_pred_change_5"] = dependency_prediction.diff(5)
    features["dep_pred_abs"] = dependency_prediction.abs()

    for lag in [1, 2, 5, 10]:
        features[f"{base_key}_ret_lag{lag}"] = base_r.shift(lag).reindex(idx)

    features[f"{base_key}_vol_5"] = base_r.rolling(5).std().reindex(idx)
    features[f"{base_key}_vol_20"] = base_r.rolling(20).std().reindex(idx)
    features[f"{base_key}_mom_5"] = base_r.rolling(5).sum().reindex(idx)
    features[f"{base_key}_mom_20"] = base_r.rolling(20).sum().reindex(idx)
    features[f"{base_key}_down_streak_5"] = (base_r < 0).astype(int).rolling(5).sum().reindex(idx)

    if "ETH-USD" in returns.columns:
        eth = returns["ETH-USD"]
        features["eth_ret_lag1"] = eth.shift(1).reindex(idx)
        features["eth_ret_lag5"] = eth.shift(5).reindex(idx)
        features[f"{base_key}_eth_spread_1"] = (base_r.shift(1) - eth.shift(1)).reindex(idx)
        features[f"{base_key}_eth_corr_14"] = rolling_corr(base_r, eth, 14).shift(1).reindex(idx)

    features[f"{base_key}_other_corr_14"] = rolling_corr(base_r, returns[other], 14).shift(1).reindex(idx)
    features[f"{base_key}_other_spread_5"] = (base_r - returns[other]).abs().rolling(5).mean().shift(1).reindex(idx)

    signal_target = build_signal_target(returns, other, horizon, mode=target_mode, stress_sigma=stress_sigma)
    return features.join(signal_target, how="inner").dropna()


def fit_predict_signal_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    min_train: int,
    refit_every: int,
    random_state: int,
    rf_n_jobs: int = -1,
) -> pd.DataFrame:
    X_values = X.values
    idx = X.index
    y_values = y.loc[idx].astype(int).values
    n_obs = len(idx)

    model_specs: Dict[str, object] = {
        "Logit": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_state)),
        "RF_Cls": RandomForestClassifier(n_estimators=100, max_depth=6, random_state=random_state, n_jobs=rf_n_jobs, class_weight="balanced_subsample"),
        # GradientBoostingClassifier does not support class_weight directly;
        # we pass sample_weight="balanced" at fit time (see training loop below).
        "GBM_Cls": GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=random_state, subsample=0.8),
    }

    # Minimum number of samples required for each class before fitting classifiers.
    # Stress events are rare (~15-20 %), so early windows may have too few positives.
    MIN_CLASS_SAMPLES = 20

    prob_preds = {name: np.full(n_obs, np.nan, dtype=float) for name in model_specs}
    fitted: Dict[str, object] = {}
    last_refit = -10**9

    for t in range(min_train, n_obs):
        train_idx = np.arange(0, t)
        if (t - last_refit) >= refit_every:
            last_refit = t
            X_train, y_train = X_values[train_idx], y_values[train_idx]

            n_pos = int(y_train.sum())
            n_neg = int(len(y_train) - n_pos)
            if n_pos < MIN_CLASS_SAMPLES or n_neg < MIN_CLASS_SAMPLES:
                # Not enough samples of each class — skip refit, keep previous models
                continue

            for name, model in model_specs.items():
                try:
                    if name == "GBM_Cls":
                        # Balanced sample weights compensate for class imbalance
                        sw = compute_sample_weight("balanced", y_train)
                        model.fit(X_train, y_train, sample_weight=sw)
                    else:
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
    """Dual-panel signal plot.

    Top panel (height ratio 3): Logit P(down) line + threshold dashed line.
    Bottom panel (height ratio 1): actual down-day events as vertical stems,
        coloured red where flagged (prob >= threshold), steel-blue otherwise.
    This avoids the 500+ overlapping full-height blue vlines that produced an
    unreadable blue wallpaper in the old single-panel design.
    """
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1,
        figsize=(14, 6),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )

    # ── Top panel: probability line ───────────────────────────────────────
    prob = signal_df[probability_column].dropna()
    ax_top.plot(prob.index, prob.values, label=f"Logit P(down)", color="#c23b22", linewidth=1.2, zorder=3)
    ax_top.axhline(threshold, linestyle="--", color="#333333", linewidth=1.0, label=f"Threshold = {threshold:.2f}", zorder=2)
    ax_top.set_ylim(-0.02, 1.02)
    ax_top.set_ylabel("P(down-day)", fontsize=10)
    ax_top.legend(ncol=2, fontsize=9, loc="upper left")
    ax_top.set_title(title, fontsize=11)
    ax_top.grid(axis="y", alpha=0.3, linewidth=0.6)

    # ── Bottom panel: actual down-day event markers ────────────────────────
    # Plot only dates where a down-event occurred (target_down == 1).
    # Colour each stem red if the model flagged it (prob >= threshold),
    # steel-blue if it was missed.
    if "target_down" in signal_df.columns:
        events = signal_df.index[signal_df["target_down"] == 1]
        # Align probability predictions with event dates
        prob_at_events = signal_df.loc[events, probability_column] if probability_column in signal_df.columns else pd.Series(dtype=float)
        flagged = events[prob_at_events.values >= threshold] if len(prob_at_events) else pd.Index([])
        missed = events[prob_at_events.values < threshold] if len(prob_at_events) else events

        # Draw as short stems at y=1; baseline at y=0
        for idx_set, color, label in [
            (flagged, "#c23b22", "Flagged down-day"),
            (missed,  "#4c8fbd", "Missed down-day"),
        ]:
            if len(idx_set):
                ax_bot.vlines(idx_set, 0, 1, color=color, linewidth=0.9, alpha=0.7, label=label)

        ax_bot.set_ylim(-0.15, 1.35)
        ax_bot.set_yticks([])
        ax_bot.set_ylabel("Down events", fontsize=9)
        ax_bot.legend(ncol=2, fontsize=8, loc="upper left")
        ax_bot.grid(False)

    ax_bot.set_xlabel("Date", fontsize=10)
    fig.tight_layout(h_pad=0.4)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def diagnose_signal_collapse(
    prob_df: pd.DataFrame,
    y_true: pd.Series,
    dependency_name: str,
    window: int,
    threshold: float,
    out_path: str,
) -> pd.DataFrame:
    """Diagnostic function to detect classifier collapse and class imbalance issues.

    Checks:
        1. Class balance ratio (n_pos / n_total)
        2. Predicted probability distribution (min, max, mean, std)
        3. Whether the predicted std is below 0.05 (near-constant output)
        4. Whether signals are ever fired (any prob >= threshold)

    Emits a UserWarning if the classifier has collapsed to near-constant output.
    Saves per-model diagnostics to `out_path`.

    Returns a DataFrame with one row per classifier model.
    """
    mask_y = y_true.notna()
    n_total = int(mask_y.sum())
    n_pos   = int(y_true.loc[mask_y].sum())
    class_balance = n_pos / n_total if n_total > 0 else np.nan

    rows = []
    for model_name in prob_df.columns:
        mask = prob_df[model_name].notna() & mask_y
        probs = prob_df.loc[mask, model_name].values
        if len(probs) == 0:
            continue
        prob_std  = float(np.std(probs))
        n_signals = int((probs >= threshold).sum())
        collapsed = prob_std < 0.05

        if collapsed:
            warnings.warn(
                f"[signal_diagnostics] {model_name} | {dependency_name} w={window}: "
                f"Classifier collapsed to near-constant output (prob_std={prob_std:.4f}) — "
                f"check class imbalance (class_balance={class_balance:.3f}) and threshold."
            )

        rows.append({
            "dependency":     dependency_name,
            "window":         window,
            "model":          model_name,
            "class_balance":  class_balance,
            "n_total":        n_total,
            "n_pos":          n_pos,
            "prob_min":       float(np.min(probs)),
            "prob_max":       float(np.max(probs)),
            "prob_mean":      float(np.mean(probs)),
            "prob_std":       prob_std,
            "threshold":      threshold,
            "n_signals_fired":n_signals,
            "signal_rate":    float(n_signals / len(probs)),
            "collapsed":      collapsed,
        })

    diag_df = pd.DataFrame(rows)
    return diag_df


def run_stress_threshold_sensitivity(
    prob_df: pd.DataFrame,
    y_true: pd.Series,
    next_returns: pd.Series,
    dependency_name: str,
    window: int,
    sigma_thresholds: Optional[list] = None,
    classification_threshold: float = 0.55,
) -> pd.DataFrame:
    """Compute signal metrics for different stress_sigma thresholds.

    Because the probability predictions (prob_df) are already computed via
    walk-forward, this function only recomputes the *target label* using
    different stress_sigma values and re-evaluates classifier metrics.
    No re-training is needed — only the target changes.

    This allows fast sensitivity analysis over the stress day definition
    without re-running the full walk-forward.

    Parameters
    ----------
    prob_df : pre-computed probability predictions from walk-forward
    y_true  : already-used target (sigma=0.75 by default)
    next_returns : raw next-day returns for the traditional asset
    sigma_thresholds : list of sigma values to evaluate
    classification_threshold : probability cut-off for binary signal

    Returns a DataFrame with columns:
        stress_sigma, model, BalancedAccuracy, F1Down, AUC, ExitRate, n_pos, n_test
    """
    if sigma_thresholds is None:
        sigma_thresholds = [0.5, 0.75, 1.0, 1.5, 2.0]

    rows = []
    for model_name in prob_df.columns:
        mask = prob_df[model_name].notna() & next_returns.notna()
        if mask.sum() < 50:
            continue
        probs = prob_df.loc[mask, model_name].astype(float)
        nr    = next_returns.loc[mask]

        # Recompute trailing vol from next_returns (approximate; real code uses returns)
        trail_vol = next_returns.rolling(20).std().shift(1).loc[mask]

        for sigma in sigma_thresholds:
            # Redefine target with this sigma
            y_sigma = (nr < (-sigma * trail_vol)).astype(int)
            valid = y_sigma.notna() & probs.notna()
            yt = y_sigma.loc[valid].values
            yp = probs.loc[valid].values
            if len(yt) < 50 or yt.sum() < 5:
                continue
            signal = (yp >= classification_threshold).astype(int)
            rows.append({
                "dependency":    dependency_name,
                "window":        window,
                "model":         model_name,
                "stress_sigma":  sigma,
                "n_pos":         int(yt.sum()),
                "n_test":        len(yt),
                "BalancedAccuracy": float(balanced_accuracy_score(yt, signal)),
                "F1Down":        float(f1_score(yt, signal, zero_division=0)),
                "AUC":           float(roc_auc_score(yt, yp)) if len(np.unique(yt)) > 1 else np.nan,
                "ExitRate":      float(signal.mean()),
            })

    return pd.DataFrame(rows)


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
    rf_n_jobs: int = -1,
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
        rf_n_jobs=rf_n_jobs,
    )
    metrics_df = compute_signal_metrics(y_signal, signal_data["next_return"], prob_df, threshold)
    if metrics_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    best_signal_model = metrics_df.iloc[0]["signal_model"]
    signal_out = pd.concat([signal_data[["next_return", "target_down"]], prob_df], axis=1)
    signal_out["best_signal_flag"] = (signal_out[best_signal_model] >= threshold).astype(float)

    metrics_df.insert(0, "dependency_model", dependency_model)
    signal_target_mode = cfg.get("signal_target_mode", "stress")
    signal_label = f"{signal_target_mode}_{other}"
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

    # ── Diagnostics: detect classifier collapse ───────────────────────────────
    try:
        diag_path = os.path.join(paths.results, "signal_diagnostics.csv")
        new_diag = diagnose_signal_collapse(
            prob_df=prob_df,
            y_true=y_signal,
            dependency_name=dependency_name,
            window=window,
            threshold=threshold,
            out_path=diag_path,
        )
        # Append to existing file if present — lock guards against concurrent writes
        # when n_parallel_workers > 1
        if not new_diag.empty:
            with _DIAG_FILE_LOCK:
                if os.path.exists(diag_path):
                    existing = pd.read_csv(diag_path)
                    pd.concat([existing, new_diag], ignore_index=True).to_csv(diag_path, index=False)
                else:
                    new_diag.to_csv(diag_path, index=False)
    except Exception as _d_exc:
        warnings.warn(f"Signal diagnostics skipped for {dependency_name} w={window}: {_d_exc}")

    # ── Stress sigma threshold sensitivity ────────────────────────────────────
    try:
        sigma_thresholds = cfg.get("sensitivity", {}).get("stress_thresholds", [0.5, 0.75, 1.0, 1.5, 2.0])
        sens_df = run_stress_threshold_sensitivity(
            prob_df=prob_df,
            y_true=y_signal,
            next_returns=signal_data["next_return"],
            dependency_name=dependency_name,
            window=window,
            sigma_thresholds=sigma_thresholds,
            classification_threshold=threshold,
        )
        if not sens_df.empty:
            sens_path = os.path.join(paths.results, "stress_threshold_sensitivity.csv")
            with _SENS_FILE_LOCK:
                if os.path.exists(sens_path):
                    existing_s = pd.read_csv(sens_path)
                    pd.concat([existing_s, sens_df], ignore_index=True).to_csv(sens_path, index=False)
                else:
                    sens_df.to_csv(sens_path, index=False)
    except Exception as _s_exc:
        warnings.warn(f"Stress threshold sensitivity skipped for {dependency_name} w={window}: {_s_exc}")

    return signal_out, metrics_df
