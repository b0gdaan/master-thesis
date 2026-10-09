"""
Leakage-safe DCC-GARCH helpers for walk-forward evaluation.
"""
import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from thesis_app.dcc import ARCH_AVAILABLE, _dcc_loglik, _fit_univariate_garch


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


def _fit_state(train: pd.DataFrame, opt_start: Optional[np.ndarray] = None) -> Dict[str, np.ndarray | float]:
    z1 = _fit_univariate_garch(train["r1"])
    z2 = _fit_univariate_garch(train["r2"])
    t_obs = min(len(z1), len(z2))
    z = np.column_stack([z1[-t_obs:], z2[-t_obs:]])
    qbar = np.cov(z.T)
    a, b = _fit_dcc_params(z, qbar, opt_start=opt_start)
    q_last = _reconstruct_q_last(z, float(a), float(b), qbar)
    return {"a": float(a), "b": float(b), "qbar": qbar, "q_last": q_last}


def dcc_garch_walk_forward_predict(
    r1: pd.Series,
    r2: pd.Series,
    min_train: int,
    refit_every: int,
    horizon: int = 1,
) -> np.ndarray:
    """
    Expanding-window DCC benchmark without future leakage.

    Between refits, predictions use the closed-form k-step-ahead DCC forecast
    implied by the latest estimated state.
    """
    if not ARCH_AVAILABLE:
        raise ImportError("arch package required: pip install arch")

    df = pd.concat([r1.rename("r1"), r2.rename("r2")], axis=1).dropna()
    if len(df) < max(min_train, 250):
        raise ValueError(f"Not enough data for DCC walk-forward: {len(df)} rows.")

    preds = pd.Series(np.nan, index=df.index, dtype=float)
    state: Optional[Dict[str, np.ndarray | float]] = None
    last_refit = -10**9
    last_opt: Optional[np.ndarray] = None

    for t in range(min_train, len(df)):
        if state is None or (t - last_refit) >= refit_every:
            train = df.iloc[: t + 1]
            state = _fit_state(train, opt_start=last_opt)
            last_refit = t
            last_opt = np.array([state["a"], state["b"]], dtype=float)

        step_ahead = horizon + (t - last_refit)
        preds.iloc[t] = _forecast_from_state(
            state["q_last"],
            state["qbar"],
            float(state["a"]),
            float(state["b"]),
            step_ahead=step_ahead,
        )

    full_index = pd.concat([r1.to_frame(), r2.to_frame()], axis=1).index
    full_pred = pd.Series(np.nan, index=full_index, dtype=float)
    full_pred.loc[df.index] = preds.values
    return full_pred.values
