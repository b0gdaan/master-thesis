import numpy as np
import pandas as pd
from typing import Tuple, Optional

from scipy.optimize import minimize

try:
    from arch import arch_model
except Exception as e:
    raise ImportError("arch is required for DCC-GARCH benchmark. Install via: python -m pip install arch") from e


def _fit_univariate_garch(r: pd.Series) -> np.ndarray:
    """
    Fit a simple GARCH(1,1) with zero mean (returns already centered enough),
    return standardized residuals (eps_t / sigma_t).
    """
    x = 100.0 * r.dropna().astype(float).values  # scale for numerical stability
    am = arch_model(x, vol="Garch", p=1, q=1, mean="Zero", dist="normal")
    res = am.fit(disp="off")
    eps = res.resid
    sig = res.conditional_volatility
    z = eps / sig
    return z


def _dcc_loglik(params: np.ndarray, z: np.ndarray) -> float:
    """
    Negative log-likelihood for DCC(1,1) with standardized residuals z (T x 2).
    Engle (2002)-style recursion:
      Q_t = (1-a-b) Qbar + a z_{t-1} z_{t-1}^T + b Q_{t-1}
      R_t = diag(Q_t)^(-1/2) Q_t diag(Q_t)^(-1/2)
    """
    a, b = params
    if a <= 0 or b <= 0 or (a + b) >= 0.999:
        return 1e12

    T = z.shape[0]
    Qbar = np.cov(z.T)
    Q = Qbar.copy()

    nll = 0.0
    for t in range(1, T):
        zz = np.outer(z[t-1], z[t-1])
        Q = (1 - a - b) * Qbar + a * zz + b * Q

        d = np.sqrt(np.diag(Q))
        Dinv = np.diag(1.0 / d)
        R = Dinv @ Q @ Dinv

        detR = np.linalg.det(R)
        if detR <= 0 or not np.isfinite(detR):
            return 1e12
        invR = np.linalg.inv(R)
        nll += 0.5 * (np.log(detR) + (z[t].T @ invR @ z[t]) - (z[t].T @ z[t]))
    return float(nll)


def dcc_garch_fit_predict(
    r1: pd.Series,
    r2: pd.Series,
    horizon: int = 1,
    opt_start: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fit DCC-GARCH(1,1) on two return series and produce 1-step ahead correlation forecasts.
    Returns:
      pred_corr: array aligned to the input index (same length), containing one-step-ahead forecasts
      in-sample_corr: DCC estimated contemporaneous correlations (R_t[0,1]) aligned similarly.
    Notes:
      - For horizon>1 we still use repeated expectation recursion (approx), but main use is h=1.
      - Output forecasts for the first few points are NaN due to recursion.
    """
    df = pd.concat([r1.rename("r1"), r2.rename("r2")], axis=1).dropna()
    if len(df) < 300:
        raise ValueError("Not enough data for DCC-GARCH (need ~300+ observations).")

    z1 = _fit_univariate_garch(df["r1"])
    z2 = _fit_univariate_garch(df["r2"])
    T = min(len(z1), len(z2))
    z = np.column_stack([z1[-T:], z2[-T:]])

    Qbar = np.cov(z.T)
    Q = Qbar.copy()

    x0 = opt_start if opt_start is not None else np.array([0.05, 0.90])
    bounds = [(1e-4, 0.5), (1e-4, 0.999)]
    cons = ({'type': 'ineq', 'fun': lambda p: 0.999 - (p[0] + p[1])},)

    res = minimize(lambda p: _dcc_loglik(p, z), x0=x0, bounds=bounds, constraints=cons, method="SLSQP")
    a, b = res.x

    # compute R_t and one-step-ahead forecast
    corr_t = np.full(T, np.nan, dtype=float)
    pred = np.full(T, np.nan, dtype=float)

    for t in range(1, T):
        zz = np.outer(z[t-1], z[t-1])
        Q = (1 - a - b) * Qbar + a * zz + b * Q

        d = np.sqrt(np.diag(Q))
        Dinv = np.diag(1.0 / d)
        R = Dinv @ Q @ Dinv
        corr_t[t] = R[0, 1]

        # one-step ahead expectation: E[z_t z_t^T | t] approx = R_t
        Q_f = (1 - a - b) * Qbar + (a + b) * Q
        d_f = np.sqrt(np.diag(Q_f))
        Dinv_f = np.diag(1.0 / d_f)
        R_f = Dinv_f @ Q_f @ Dinv_f
        pred[t] = R_f[0, 1]

    # align back to original index (df.index corresponds to z, but we trimmed to last T)
    idx = df.index[-T:]
    pred_s = pd.Series(pred, index=idx).reindex(df.index)
    corr_s = pd.Series(corr_t, index=idx).reindex(df.index)

    # expand to full input index
    full_pred = pd.Series(np.nan, index=pd.concat([r1, r2], axis=1).index)
    full_corr = full_pred.copy()
    full_pred.loc[df.index] = pred_s.values
    full_corr.loc[df.index] = corr_s.values

    return full_pred.values, full_corr.values
