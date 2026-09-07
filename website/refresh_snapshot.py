"""Create the dated model snapshot consumed by the static thesis website.

The public page cannot run Python or obtain market data itself. This script pulls
public Yahoo Finance closes, rebuilds the thesis feature set and exports one
auditable JSON snapshot. Run it manually before publishing a new site version.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("latest_snapshot.json")
TICKERS = ["BTC-USD", "ETH-USD", "^GSPC", "^IXIC", "GLD", "SLV", "UUP"]
BASE = "BTC-USD"
OTHER = "^GSPC"
WINDOW = 30
MIN_TRAIN = 800
STRESS_SIGMA = 0.75
WEB_FEATURES = [
    "dep_pred",
    "btcusd_ret_abs",
    "btcusd_vol_20_norm",
    "btcusd_mom_5_abs",
    "dep_pred_change_1",
]


def close_prices() -> tuple[pd.DataFrame, pd.Timestamp]:
    """Download public closes and retain the thesis's two-day weekend fill."""
    end = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() + pd.Timedelta(days=1)
    raw = yf.download(
        TICKERS,
        start="2016-01-01",
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        group_by="column",
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no price data.")
    close = raw["Close"].copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    last_equity_close = close[OTHER].dropna().index[-1]
    aligned = close.dropna(how="all").ffill(limit=2).dropna().sort_index()
    return aligned, last_equity_close


def fisher_z(rho: pd.Series | float) -> pd.Series | float:
    return np.arctanh(np.clip(rho, -1 + 1e-6, 1 - 1e-6))


def ar1_prediction(z: pd.Series) -> tuple[float, float, pd.Series]:
    """Fit the AR(1) specification used by the thesis demonstrator."""
    frame = pd.concat([z.rename("y"), z.shift(1).rename("lag1")], axis=1).dropna()
    frame = frame.iloc[MIN_TRAIN:]
    model = LinearRegression().fit(frame[["lag1"]], frame["y"])
    lagged = z.shift(1).dropna().rename("lag1")
    predictions = pd.Series(
        model.predict(lagged.to_frame()),
        index=lagged.index,
        name="dep_pred",
    )
    return float(model.intercept_), float(model.coef_[0]), predictions


def signal_frame(returns: pd.DataFrame, dep_pred: pd.Series) -> pd.DataFrame:
    """Mirror the five browser features derived in train_signal_model.py."""
    frame = pd.DataFrame(index=dep_pred.index)
    btc = returns[BASE]
    spx = returns[OTHER]
    frame["dep_pred"] = dep_pred
    frame["dep_pred_change_1"] = dep_pred.diff(1)
    frame["btcusd_ret_abs"] = btc.shift(1).abs().reindex(frame.index)
    frame["btcusd_vol_20_norm"] = btc.rolling(20).std().reindex(frame.index) / 0.55
    frame["btcusd_mom_5_abs"] = btc.rolling(5).sum().abs().reindex(frame.index)
    next_return = spx.shift(-1).reindex(frame.index)
    trailing_vol = spx.rolling(20).std().reindex(frame.index)
    frame["target_down"] = (next_return < -STRESS_SIGMA * trailing_vol).astype(float)
    frame.loc[next_return.isna(), "target_down"] = np.nan
    return frame.dropna()


def raw_coefficients(pipe, features: list[str]) -> tuple[float, dict[str, float]]:
    scaler = pipe.named_steps["standardscaler"]
    model = pipe.named_steps["logisticregression"]
    raw = model.coef_[0] / scaler.scale_
    intercept = float(model.intercept_[0] - np.dot(raw, scaler.mean_))
    return intercept, {name: float(value) for name, value in zip(features, raw)}


def main() -> None:
    prices, last_equity_close = close_prices()
    returns = np.log(prices / prices.shift(1)).dropna().sort_index()
    rho = returns[BASE].rolling(WINDOW).corr(returns[OTHER]).dropna()
    z = pd.Series(fisher_z(rho), index=rho.index, name="z")
    intercept, beta, dep_pred_history = ar1_prediction(z)
    training = signal_frame(returns, dep_pred_history)

    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.10, max_iter=3000, class_weight="balanced", random_state=42),
    )
    pipe.fit(training[WEB_FEATURES], training["target_down"].astype(int))
    logit_intercept, coefficients = raw_coefficients(pipe, WEB_FEATURES)

    # The latest aligned day has BTC data plus the two-day S&P 500 weekend fill.
    as_of = returns.index[-1]
    z_now = float(z.loc[as_of])
    z_next = intercept + beta * z_now
    prior_prediction = intercept + beta * float(z.iloc[-2])
    latest = pd.DataFrame(
        [{
            "dep_pred": z_next,
            "btcusd_ret_abs": abs(float(returns.loc[as_of, BASE])),
            "btcusd_vol_20_norm": float(returns[BASE].rolling(20).std().loc[as_of] / 0.55),
            "btcusd_mom_5_abs": abs(float(returns[BASE].rolling(5).sum().loc[as_of])),
            "dep_pred_change_1": z_next - prior_prediction,
        }]
    )
    probability = float(pipe.predict_proba(latest[WEB_FEATURES])[0, 1])
    annualised_volatility = float(returns[BASE].rolling(20).std().loc[as_of] * np.sqrt(365))
    momentum_5 = float(returns[BASE].rolling(5).sum().loc[as_of])

    snapshot = {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "as_of_date": as_of.date().isoformat(),
        "sp500_last_close_date": last_equity_close.date().isoformat(),
        "forecast_for": (as_of + pd.Timedelta(days=1)).date().isoformat(),
        "pair": "BTC-USD / S&P 500",
        "window_days": WINDOW,
        "forecast_correlation": round(float(np.tanh(z_next)), 4),
        "forecast_fisher_z": round(z_next, 6),
        "current_correlation": round(float(rho.loc[as_of]), 4),
        "stress_probability": round(probability, 4),
        "inputs": {
            "btc_daily_return": round(float(returns.loc[as_of, BASE]), 6),
            "btc_annualised_volatility": round(annualised_volatility, 6),
            "btc_momentum_5d": round(momentum_5, 6),
        },
        "ar1": {"intercept": round(intercept, 8), "beta": round(beta, 8)},
        "logit": {"intercept": round(logit_intercept, 8), "coefficients": {k: round(v, 8) for k, v in coefficients.items()}},
        "method_note": "Static research snapshot. Prices are public Yahoo Finance adjusted closes; model features and coefficients follow the thesis web demonstrator.",
    }
    OUT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
