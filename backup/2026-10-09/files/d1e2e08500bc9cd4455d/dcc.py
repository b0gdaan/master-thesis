"""
DCC-GARCH(1,1) benchmark — Engle (2002).
Used as the econometric baseline for correlation forecasting.
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
    sig = res.conditional_volatility
    # Avoid division by zero
    sig = np.where(sig < 1e-10, 1e-10, sig)
    return eps / sig


def _dcc_loglik(params: np.ndarray, z: np.ndarray, Qbar: np.ndarray) -> float:
    """
    Negative log-likelihood for DCC(1,1) with standardized residuals z (T x 2).
    Q_t = (1-a-b)*Qbar + a*z_{t-1}*z_{t-1}^T + b*Q_{t-1}
    R_t = diag(Q_t)^(-1/2) * Q_t * diag(Q_t)^(-1/2)
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

        d = np.sqrt(np.diag(Q))
        if np.any(d < 1e-10):
            return 1e12
        Dinv = np.diag(1.0 / d)
        R = Dinv @ Q @ Dinv

        # Clip R for numerical stability
        R = np.clip(R, -0.9999, 0.9999)
        np.fill_diagonal(R, 1.0)

        detR = np.linalg.det(R)
        if detR <= 1e-15 or not np.isfinite(detR):
            return 1e12

        invR = np.linalg.inv(R)
        nll += 0.5 * (np.log(detR) + (z[t] @ invR @ z[t]) - (z[t] @ z[t]))

    return float(nll)


def dcc_garch_fit_predict(
    r1: pd.Series,
    r2: pd.Series,
    horizon: int = 1,
    opt_start: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fit DCC-GARCH(1,1) on two return series and produce 1-step ahead correlation forecasts.

    Returns
    -------
    full_pred : np.ndarray  — one-step-ahead forecasted correlation, aligned to input index
    full_corr : np.ndarray  — in-sample DCC correlation (contemporaneous)
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

    # Reconstruct R_t and one-step-ahead forecasts
    Q = Qbar.copy()
    corr_t = np.full(T, np.nan, dtype=float)
    pred = np.full(T, np.nan, dtype=float)

    for t in range(1, T):
        zz = np.outer(z[t - 1], z[t - 1])
        Q = (1.0 - a - b) * Qbar + a * zz + b * Q

        d = np.sqrt(np.diag(Q))
        Dinv = np.diag(1.0 / d)
        R = Dinv @ Q @ Dinv
        corr_t[t] = float(np.clip(R[0, 1], -0.9999, 0.9999))

        # One-step-ahead: E[Q_{t+1}] = (1-a-b)*Qbar + (a+b)*Q
        Q_f = (1.0 - a - b) * Qbar + (a + b) * Q
        d_f = np.sqrt(np.diag(Q_f))
        Dinv_f = np.diag(1.0 / d_f)
        R_f = Dinv_f @ Q_f @ Dinv_f
        pred[t] = float(np.clip(R_f[0, 1], -0.9999, 0.9999))

    idx = df.index[-T:]
    pred_s = pd.Series(pred, index=idx).reindex(df.index)
    corr_s = pd.Series(corr_t, index=idx).reindex(df.index)

    # Expand to full original index
    full_idx = pd.concat([r1.to_frame(), r2.to_frame()], axis=1).index
    full_pred = pd.Series(np.nan, index=full_idx, dtype=float)
    full_corr = pd.Series(np.nan, index=full_idx, dtype=float)
    full_pred.loc[df.index] = pred_s.values
    full_corr.loc[df.index] = corr_s.values

    return full_pred.values, full_corr.values
