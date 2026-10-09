"""
DCC-GARCH(1,1) benchmark — Engle (2002).
Used as the econometric baseline for correlation forecasting.

For the bivariate case the inner log-likelihood loop uses closed-form
scalar formulas for the 2×2 determinant and inverse, avoiding the overhead
of np.linalg on tiny matrices.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional

from scipy.optimize import minimize

try:
    from arch import arch_model
    ARCH_AVAILABLE = True
except Exception:
    ARCH_AVAILABLE = False


def _fit_univariate_garch(r: pd.Series) -> np.ndarray:
    """
    Fit GARCH(1,1) with zero mean on a return series.
    Returns standardized residuals z_t = eps_t / sigma_t.
    """
    if not ARCH_AVAILABLE:
        raise ImportError("arch package required: pip install arch")

    x = 100.0 * r.dropna().astype(float).values  # scale for numerical stability
    am = arch_model(x, vol="Garch", p=1, q=1, mean="Zero", dist="normal")
    res = am.fit(disp="off", show_warning=False)
    eps = res.resid
    sig = np.maximum(res.conditional_volatility, 1e-10)
    return eps / sig


def _fit_garch_state(r: pd.Series) -> dict:
    """
    Fit GARCH(1,1) with zero mean and return standardized residuals together
    with the model parameters needed for incremental out-of-sample updates.

    Returns a dict with keys:
      z        – standardized residuals eps_t / sigma_t (ndarray, shape T)
      omega    – variance intercept (in scaled units, scale=100)
      alpha    – ARCH coefficient
      beta     – GARCH coefficient
      last_h   – conditional variance at the last observation (scaled units)
      last_eps – scaled residual at the last observation (scale * r[-1])
      scale    – multiplicative scale applied to raw returns (100.0)
    """
    if not ARCH_AVAILABLE:
        raise ImportError("arch package required: pip install arch")

    scale = 100.0
    x = scale * r.dropna().astype(float).values
    am = arch_model(x, vol="Garch", p=1, q=1, mean="Zero", dist="normal")
    res = am.fit(disp="off", show_warning=False)

    # Extract omega, alpha, beta from fitted params; use positional fallback
    # because arch may use different key names across versions.
    params = res.params
    try:
        omega = float(params["omega"])
        alpha = float(params["alpha[1]"])
        beta  = float(params["beta[1]"])
    except (KeyError, TypeError):
        vals = np.asarray(params, dtype=float)
        omega, alpha, beta = vals[0], vals[1], vals[2]

    eps = res.resid
    sig = np.maximum(res.conditional_volatility, 1e-10)

    return {
        "z":        eps / sig,
        "omega":    omega,
        "alpha":    alpha,
        "beta":     beta,
        "last_h":   float(sig[-1] ** 2),
        "last_eps": float(eps[-1]),
        "scale":    scale,
    }


def _dcc_loglik(params: np.ndarray, z: np.ndarray, Qbar: np.ndarray) -> float:
    """
    Negative log-likelihood for bivariate DCC(1,1).

    Q_t = (1-a-b)*Qbar + a * z_{t-1} z_{t-1}' + b * Q_{t-1}
    R_t = diag(Q_t)^{-1/2} Q_t diag(Q_t)^{-1/2}

    For the 2×2 case the determinant and quadratic form are computed via
    scalar arithmetic, which is significantly faster than np.linalg on tiny
    matrices.
    """
    a, b = params
    if a <= 0 or b <= 0 or (a + b) >= 0.9999:
        return 1e12

    T = z.shape[0]
    Q = Qbar.copy()
    nll = 0.0

    for t in range(1, T):
        zz = np.outer(z[t - 1], z[t - 1])
        Q = (1.0 - a - b) * Qbar + a * zz + b * Q

        d0 = Q[0, 0]
        d1 = Q[1, 1]
        if d0 < 1e-10 or d1 < 1e-10:
            return 1e12

        # Correlation coefficient from Q
        rho = Q[0, 1] / (np.sqrt(d0) * np.sqrt(d1))
        rho = max(-0.9999, min(0.9999, rho))

        # 2×2 scalar formulas: det(R) = 1 - rho^2,  z' R^{-1} z
        det_r = 1.0 - rho * rho
        if det_r <= 1e-15:
            return 1e12

        z0, z1 = z[t, 0], z[t, 1]
        zRinvz = (z0 * z0 + z1 * z1 - 2.0 * rho * z0 * z1) / det_r
        nll += 0.5 * (np.log(det_r) + zRinvz - (z0 * z0 + z1 * z1))

    return float(nll)


def dcc_garch_fit_predict(
    r1: pd.Series,
    r2: pd.Series,
    horizon: int = 1,
    opt_start: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fit DCC-GARCH(1,1) on two return series and produce 1-step ahead
    correlation forecasts (in-sample, for diagnostic use only).

    For leakage-safe walk-forward evaluation use dcc_garch_walk_forward_predict
    from dcc_walk.py instead.

    Returns
    -------
    full_pred : ndarray — one-step-ahead forecasted correlation, aligned to input index
    full_corr : ndarray — in-sample DCC correlation (contemporaneous)
    """
    if not ARCH_AVAILABLE:
        raise ImportError("arch package required: pip install arch")

    df = pd.concat([r1.rename("r1"), r2.rename("r2")], axis=1).dropna()
    if len(df) < 250:
        raise ValueError(f"Not enough data for DCC-GARCH: {len(df)} rows (need ≥250).")

    z1 = _fit_univariate_garch(df["r1"])
    z2 = _fit_univariate_garch(df["r2"])
    T = min(len(z1), len(z2))
    z = np.column_stack([z1[-T:], z2[-T:]])

    Qbar = np.cov(z.T)
    x0 = opt_start if opt_start is not None else np.array([0.05, 0.90])
    bounds = [(1e-4, 0.49), (1e-4, 0.9989)]
    cons = ({"type": "ineq", "fun": lambda p: 0.9999 - (p[0] + p[1])},)

    res = minimize(
        lambda p: _dcc_loglik(p, z, Qbar),
        x0=x0,
        bounds=bounds,
        constraints=cons,
        method="SLSQP",
        options={"maxiter": 500, "ftol": 1e-9},
    )
    a, b = res.x

    Q = Qbar.copy()
    corr_t = np.full(T, np.nan, dtype=float)
    pred = np.full(T, np.nan, dtype=float)

    for t in range(1, T):
        zz = np.outer(z[t - 1], z[t - 1])
        Q = (1.0 - a - b) * Qbar + a * zz + b * Q

        d = np.sqrt(np.maximum(np.diag(Q), 1e-10))
        rho = Q[0, 1] / (d[0] * d[1])
        corr_t[t] = float(np.clip(rho, -0.9999, 0.9999))

        # One-step-ahead: E[Q_{t+1}] = (1-a-b)*Qbar + (a+b)*Q_t
        Q_f = (1.0 - a - b) * Qbar + (a + b) * Q
        d_f = np.sqrt(np.maximum(np.diag(Q_f), 1e-10))
        rho_f = Q_f[0, 1] / (d_f[0] * d_f[1])
        pred[t] = float(np.clip(rho_f, -0.9999, 0.9999))

    idx = df.index[-T:]
    full_idx = pd.concat([r1.to_frame(), r2.to_frame()], axis=1).index
    full_pred = pd.Series(np.nan, index=full_idx, dtype=float)
    full_corr = pd.Series(np.nan, index=full_idx, dtype=float)
    full_pred.loc[idx] = pred
    full_corr.loc[idx] = corr_t

    return full_pred.values, full_corr.values
