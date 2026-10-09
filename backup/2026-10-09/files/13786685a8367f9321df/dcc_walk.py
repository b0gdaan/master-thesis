"""
Leakage-safe DCC-GARCH helpers for walk-forward evaluation.

Between scheduled refits the GARCH conditional variance for each series is
advanced one step at a time using the last fitted parameters, and the DCC Q
matrix is updated with the resulting standardized residual.  This produces a
genuine 1-step-ahead forecast at every point rather than an increasingly
stale multi-step geometric-decay approximation.
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
    """Estimate DCC(1,1) parameters a, b via SLSQP with stationarity constraint."""
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
    """Replay the DCC Q recursion over the full training sample to obtain Q_T."""
    q_t = qbar.copy()
    for t in range(1, z.shape[0]):
        zz = np.outer(z[t - 1], z[t - 1])
        q_t = (1.0 - a - b) * qbar + a * zz + b * q_t
    return q_t


def _forecast_from_state(
    q_last: np.ndarray,
    qbar: np.ndarray,
    a: float,
    b: float,
    step_ahead: int = 1,
) -> float:
    """
    Closed-form h-step-ahead DCC correlation forecast from the current Q state.

    E[Q_{t+h} | Q_t] = (1 - (a+b)^h) * Qbar + (a+b)^h * Q_t

    For step_ahead=1 (the default) this reduces to the standard one-step formula.
    """
    decay = (a + b) ** max(step_ahead, 1)
    q_forecast = (1.0 - decay) * qbar + decay * q_last
    d = np.sqrt(np.maximum(np.diag(q_forecast), 1e-10))
    rho = q_forecast[0, 1] / (d[0] * d[1])
    return float(np.clip(rho, -0.9999, 0.9999))


def _update_garch_z(r_new: float, garch_state: dict) -> tuple:
    """
    Advance a GARCH(1,1) state one step with a new raw log-return.

    Uses the variance recursion:
        h_t = omega + alpha * eps_{t-1}^2 + beta * h_{t-1}
        z_t = (scale * r_t) / sqrt(h_t)

    Parameters
    ----------
    r_new       : raw (unscaled) log-return for the new observation
    garch_state : dict from _fit_garch_state or a previous call to this function

    Returns
    -------
    z_new   : float – standardized residual for the new period
    updated : dict  – garch_state with last_h and last_eps advanced by one step
    """
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


def _fit_state(
    train: pd.DataFrame,
    opt_start: Optional[np.ndarray] = None,
) -> Dict:
    """
    Fit DCC-GARCH on the training window and return the full state dict needed
    for both one-step-ahead forecasting and incremental GARCH updates.

    State keys
    ----------
    a, b      – estimated DCC parameters
    qbar      – unconditional correlation matrix of standardized residuals
    q_last    – Q matrix at the last training observation
    last_z    – standardized residual pair [z1, z2] at the last observation;
                used as z_{t-1} in the first post-refit Q update
    garch1/2  – GARCH state dicts with omega, alpha, beta, last_h, last_eps, scale
    """
    g1 = _fit_garch_state(train["r1"])
    g2 = _fit_garch_state(train["r2"])
    t_obs = min(len(g1["z"]), len(g2["z"]))
    z = np.column_stack([g1["z"][-t_obs:], g2["z"][-t_obs:]])
    qbar = np.cov(z.T)
    a, b = _fit_dcc_params(z, qbar, opt_start=opt_start)
    q_last = _reconstruct_q_last(z, float(a), float(b), qbar)
    return {
        "a":      float(a),
        "b":      float(b),
        "qbar":   qbar,
        "q_last": q_last,
        "last_z": z[-1].copy(),  # used as z_{t-1} in the first incremental Q step
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
    Expanding-window DCC-GARCH benchmark without future data leakage.

    At each time step t a h-step-ahead DCC correlation forecast is produced
    using only information available up to and including t.

    Between scheduled refits the GARCH conditional variances are updated
    one step at a time using the last fitted parameters so that Q_t and the
    standardized residuals stay current.  This avoids the increasing error
    that would result from freezing the state at the last refit and relying
    on the geometric-decay multi-step approximation alone.

    Parameters
    ----------
    r1, r2      : aligned daily log-return series
    min_train   : minimum number of observations before the first forecast
    refit_every : how often (in observations) the full DCC fit is repeated
    horizon     : forecast horizon in steps (default 1)
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
            # Full refit on the expanding training window [0 .. t]
            state = _fit_state(df.iloc[: t + 1], opt_start=last_opt)
            last_refit = t
            last_opt = np.array([state["a"], state["b"]], dtype=float)
        else:
            # Incremental update: advance GARCH and Q one step with the actual
            # new return at time t so the state reflects all available data.
            r1_t = float(df["r1"].iloc[t])
            r2_t = float(df["r2"].iloc[t])
            z1_new, state["garch1"] = _update_garch_z(r1_t, state["garch1"])
            z2_new, state["garch2"] = _update_garch_z(r2_t, state["garch2"])
            z_t = np.array([z1_new, z2_new])

            # Q_t = (1-a-b)*Qbar + a * z_{t-1} z_{t-1}' + b * Q_{t-1}
            a_val, b_val = state["a"], state["b"]
            state["q_last"] = (
                (1.0 - a_val - b_val) * state["qbar"]
                + a_val * np.outer(state["last_z"], state["last_z"])
                + b_val * state["q_last"]
            )
            state["last_z"] = z_t  # stored for use as z_{t-1} in the next step

        # h-step-ahead forecast from the current (freshly updated) Q state
        preds.iloc[t] = _forecast_from_state(
            state["q_last"], state["qbar"], state["a"], state["b"],
            step_ahead=horizon,
        )

    full_index = pd.concat([r1.to_frame(), r2.to_frame()], axis=1).index
    full_pred = pd.Series(np.nan, index=full_index, dtype=float)
    full_pred.loc[df.index] = preds.values
    return full_pred.values
