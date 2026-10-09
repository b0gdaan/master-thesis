"""
Leakage-safe DCC-GARCH helpers for walk-forward evaluation.
"""
import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from thesis_app.dcc import ARCH_AVAILABLE, _dcc_loglik, _fit_garch_state


def _fit_dcc_params(
    z: np.ndarray,
    qbar: np.ndarray,
    opt_start: Optional[np.ndarray] = None,
) -> np.ndarray:
    x0 = opt_start if opt_start is not None else np.array([0.05, 0.90], dtype=float)
    bounds = [(1e-4, 0.49), (1e-4, 0.9989)]
    constraints = ({"type": "ineq", "fun": lambda p: 0.9999 - (p[0] + p[1])},)

    result = minimize(
        lambda p: _dcc_loglik(p, z, qbar),
        x0=x0,
        bounds=bounds,
        constraints=constraints,
        method="SLSQP",
        options={"maxiter": 500, "ftol": 1e-9},
    )
    if not result.success:
        warnings.warn(f"DCC optimization did not fully converge: {result.message}")
    return result.x.astype(float)


def _reconstruct_q_last(z: np.ndarray, a: float, b: float, qbar: np.ndarray) -> np.ndarray:
    q_t = qbar.copy()
    for t in range(1, z.shape[0]):
        zz = np.outer(z[t - 1], z[t - 1])
        q_t = (1.0 - a - b) * qbar + a * zz + b * q_t
    return q_t


def _forecast_from_state(q_last: np.ndarray, qbar: np.ndarray, a: float, b: float, step_ahead: int) -> float:
    decay = (a + b) ** max(step_ahead, 1)
    q_forecast = (1.0 - decay) * qbar + decay * q_last
    diag = np.sqrt(np.clip(np.diag(q_forecast), 1e-10, None))
    d_inv = np.diag(1.0 / diag)
    r_forecast = d_inv @ q_forecast @ d_inv
    return float(np.clip(r_forecast[0, 1], -0.9999, 0.9999))


def _update_garch_z(r_new: float, garch_state: dict) -> tuple:
    """Advance the GARCH(1,1) variance one step and return the new standardised residual."""
    eps = garch_state["scale"] * r_new
    h = (
        garch_state["omega"]
        + garch_state["alpha"] * garch_state["last_eps"] ** 2
        + garch_state["beta"]  * garch_state["last_h"]
    )
    h = max(h, 1e-10)
    z = eps / np.sqrt(h)
    updated = {**garch_state, "last_h": h, "last_eps": eps}
    return z, updated


def _fit_state(train: pd.DataFrame, opt_start: Optional[np.ndarray] = None) -> Dict:
    """Fit GARCH(1,1) for each series and DCC(1,1) on the joint residuals.

    Returns a state dict containing DCC parameters, the current Q matrix, the
    most recent standardised-residual pair, and the per-series GARCH states
    needed for incremental one-step updates between refits.
    """
    g1 = _fit_garch_state(train["r1"])
    g2 = _fit_garch_state(train["r2"])
    t_obs = min(len(g1["z"]), len(g2["z"]))
    z = np.column_stack([g1["z"][-t_obs:], g2["z"][-t_obs:]])
    qbar = np.cov(z.T)
    a, b = _fit_dcc_params(z, qbar, opt_start=opt_start)
    q_last = _reconstruct_q_last(z, float(a), float(b), qbar)
    return {
        "a": float(a),
        "b": float(b),
        "qbar": qbar,
        "q_last": q_last,
        "last_z": z[-1].copy(),
        "garch1": g1,
        "garch2": g2,
    }


def dcc_garch_walk_forward_predict(
    r1: pd.Series,
    r2: pd.Series,
    min_train: int,
    refit_every: int,
    horizon: int = 1,
) -> np.ndarray:
    """
    Expanding-window DCC benchmark without future leakage.

    On refit steps the GARCH and DCC parameters are re-estimated from scratch.
    Between refits the GARCH conditional variance is propagated forward one day
    at a time using the fitted GARCH recursion, so the DCC forecast is always a
    genuine horizon-step-ahead forecast rather than an increasingly stale one.
    """
    if not ARCH_AVAILABLE:
        raise ImportError("arch package required: pip install arch")

    df = pd.concat([r1.rename("r1"), r2.rename("r2")], axis=1).dropna()
    if len(df) < max(min_train, 250):
        raise ValueError(f"Not enough data for DCC walk-forward: {len(df)} rows.")

    preds = pd.Series(np.nan, index=df.index, dtype=float)
    state: Optional[Dict] = None
    last_refit = -(10 ** 9)
    last_opt: Optional[np.ndarray] = None

    for t in range(min_train, len(df)):
        if state is None or (t - last_refit) >= refit_every:
            train = df.iloc[: t + 1]
            state = _fit_state(train, opt_start=last_opt)
            last_refit = t
            last_opt = np.array([state["a"], state["b"]], dtype=float)
        else:
            # Advance each GARCH one step with the new observation
            z1_new, state["garch1"] = _update_garch_z(float(df["r1"].iloc[t]), state["garch1"])
            z2_new, state["garch2"] = _update_garch_z(float(df["r2"].iloc[t]), state["garch2"])
            a, b = state["a"], state["b"]
            zz = np.outer(state["last_z"], state["last_z"])
            state["q_last"] = (1.0 - a - b) * state["qbar"] + a * zz + b * state["q_last"]
            state["last_z"] = np.array([z1_new, z2_new])

        preds.iloc[t] = _forecast_from_state(
            state["q_last"],
            state["qbar"],
            float(state["a"]),
            float(state["b"]),
            step_ahead=horizon,
        )

    full_index = pd.concat([r1.to_frame(), r2.to_frame()], axis=1).index
    full_pred = pd.Series(np.nan, index=full_index, dtype=float)
    full_pred.loc[df.index] = preds.values
    return full_pred.values
