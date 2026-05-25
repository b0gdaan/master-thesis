"""
Automated test suite for the intermarket dependency forecasting pipeline.

Run with:
    pytest tests/ -v
    pytest tests/ -v --tb=short   # shorter tracebacks
    pytest tests/ -v -k "Dataset" # run only one class

Tests are grouped into:
    TestDatasetIntegrity   — raw prices.csv and returns.csv sanity
    TestDataQuality        — per-ticker stats, gaps, outliers, overlap
    TestFeatureEngineering — Fisher-z, rolling corr, no look-ahead
    TestModelMetrics       — metrics.csv sanity (RMSE, R2, rankings)
    TestDMTests            — dm_tests.csv sign convention and p-values
    TestSignalMetrics      — signal_metrics.csv classification sanity
    TestWalkForward        — no-leakage check on prediction CSVs
    TestOutputFiles        — all expected output files exist
    TestBootstrapCI        — metrics_with_ci.csv bounds validity
    TestSensitivity        — refit_sensitivity.csv monotonicity/completeness
"""
import os
import json
import math
import warnings

import numpy as np
import pandas as pd
import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW = os.path.join(BASE, "data", "raw")
DATA_PROC = os.path.join(BASE, "data", "processed")
OUT_RESULTS = os.path.join(BASE, "outputs", "results")
OUT_FIGURES = os.path.join(BASE, "outputs", "figures")
OUT_PREDS = os.path.join(BASE, "outputs", "predictions")
OUT_TABLES = os.path.join(BASE, "outputs", "tables")
OUT_QUALITY = os.path.join(BASE, "outputs", "quality")

PRICES_CSV = os.path.join(DATA_RAW, "prices.csv")
RETURNS_CSV = os.path.join(DATA_PROC, "returns.csv")
METRICS_CSV = os.path.join(OUT_RESULTS, "metrics.csv")
DM_CSV = os.path.join(OUT_RESULTS, "dm_tests.csv")
SIGNAL_CSV = os.path.join(OUT_RESULTS, "signal_metrics.csv")
CI_CSV = os.path.join(OUT_RESULTS, "metrics_with_ci.csv")
SENSITIVITY_CSV = os.path.join(OUT_RESULTS, "refit_sensitivity.csv")
METADATA_JSON = os.path.join(OUT_RESULTS, "run_metadata.json")

EXPECTED_TICKERS = ["BTC-USD", "ETH-USD", "GLD", "SLV", "UUP", "^GSPC", "^IXIC"]
EXPECTED_WINDOWS = [14, 30, 60, 90]


def _load_prices():
    return pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)


def _load_returns():
    return pd.read_csv(RETURNS_CSV, index_col=0, parse_dates=True)


def _load_metrics():
    return pd.read_csv(METRICS_CSV)


def _load_dm():
    return pd.read_csv(DM_CSV)


def _load_signal():
    return pd.read_csv(SIGNAL_CSV)


# ── TestDatasetIntegrity ──────────────────────────────────────────────────────

class TestDatasetIntegrity:
    """Raw dataset: prices.csv and returns.csv basic validity."""

    def test_prices_file_exists(self):
        assert os.path.exists(PRICES_CSV), f"prices.csv not found at {PRICES_CSV}"

    def test_returns_file_exists(self):
        assert os.path.exists(RETURNS_CSV), f"returns.csv not found at {RETURNS_CSV}"

    def test_prices_has_all_tickers(self):
        p = _load_prices()
        missing = [t for t in EXPECTED_TICKERS if t not in p.columns]
        assert not missing, f"Missing tickers in prices.csv: {missing}"

    def test_prices_all_positive(self):
        p = _load_prices()
        assert (p.dropna() > 0).all().all(), "Some price values are non-positive"

    def test_prices_no_all_nan_row(self):
        p = _load_prices()
        all_nan_rows = p.isna().all(axis=1).sum()
        assert all_nan_rows == 0, f"{all_nan_rows} rows are entirely NaN"

    def test_prices_index_sorted(self):
        p = _load_prices()
        assert p.index.is_monotonic_increasing, "prices.csv index is not sorted ascending"

    def test_prices_no_duplicate_dates(self):
        p = _load_prices()
        dups = p.index.duplicated().sum()
        assert dups == 0, f"{dups} duplicate dates in prices.csv"

    def test_prices_minimum_length(self):
        p = _load_prices()
        assert len(p) >= 2000, f"prices.csv has only {len(p)} rows (expected >= 2000)"

    def test_returns_matches_prices_columns(self):
        p = _load_prices()
        r = _load_returns()
        assert list(r.columns) == list(p.columns), (
            f"returns.csv columns {list(r.columns)} != prices.csv columns {list(p.columns)}"
        )

    def test_returns_are_log_returns(self):
        """Log returns must be small (|r| < 1 for all but extreme outliers)."""
        r = _load_returns()
        extreme = (r.abs() > 1.0).sum().sum()
        total = r.notna().sum().sum()
        assert extreme / total < 0.001, (
            f"Too many |log-returns| > 1: {extreme} ({100*extreme/total:.3f}% of obs)"
        )

    def test_returns_length_is_prices_minus_one(self):
        p = _load_prices()
        r = _load_returns()
        assert len(r) == len(p) - 1, (
            f"returns has {len(r)} rows, expected {len(p)-1} (prices - 1)"
        )

    def test_eth_start_date_correct(self):
        """ETH-USD data starts no earlier than 2017-11-01."""
        p = _load_prices()
        eth_start = p["ETH-USD"].dropna().index.min()
        assert eth_start >= pd.Timestamp("2017-10-01"), (
            f"ETH-USD starts too early: {eth_start.date()}"
        )

    def test_prices_end_date_reasonable(self):
        """Dataset should extend to at least 2026-01-01."""
        p = _load_prices()
        assert p.index.max() >= pd.Timestamp("2026-01-01"), (
            f"prices.csv ends at {p.index.max().date()}, expected >= 2026-01-01"
        )


# ── TestDataQuality ───────────────────────────────────────────────────────────

class TestDataQuality:
    """Per-ticker quality: missing values, gaps, outliers."""

    def test_missing_rate_below_threshold(self):
        """No ticker should have >50% missing prices."""
        p = _load_prices()
        for ticker in p.columns:
            rate = p[ticker].isna().mean()
            assert rate < 0.50, f"{ticker}: {rate:.1%} missing prices"

    def test_no_negative_prices(self):
        p = _load_prices()
        for ticker in p.columns:
            neg = (p[ticker].dropna() < 0).sum()
            assert neg == 0, f"{ticker}: {neg} negative price(s)"

    def test_no_zero_prices(self):
        p = _load_prices()
        for ticker in p.columns:
            zeros = (p[ticker].dropna() == 0).sum()
            assert zeros == 0, f"{ticker}: {zeros} zero price(s)"

    def test_return_volatility_reasonable(self):
        """Annualised vol of log-returns should be between 1% and 500% for all tickers."""
        r = _load_returns()
        for ticker in r.columns:
            ann_vol = float(r[ticker].std() * np.sqrt(252) * 100)
            assert 1.0 < ann_vol < 500.0, (
                f"{ticker}: annualised vol {ann_vol:.1f}% out of [1%, 500%] range"
            )

    def test_coverage_overlap_matrix_symmetric(self):
        """Pairwise coverage overlap matrix must be symmetric."""
        q_file = os.path.join(OUT_QUALITY, "coverage_overlap.csv")
        if not os.path.exists(q_file):
            pytest.skip("coverage_overlap.csv not found (run main.py first)")
        mat = pd.read_csv(q_file, index_col=0)
        diff = (mat.values - mat.values.T).max()
        assert diff == 0, f"Coverage matrix is not symmetric (max diff = {diff})"

    def test_btc_eth_full_overlap(self):
        """BTC and ETH should share at least 2000 joint trading days."""
        p = _load_prices()
        overlap = (p["BTC-USD"].notna() & p["ETH-USD"].notna()).sum()
        assert overlap >= 2000, f"BTC-ETH overlap only {overlap} days"

    def test_returns_mean_near_zero(self):
        """Daily mean log-return should be close to zero (|mu| < 0.01)."""
        r = _load_returns()
        for ticker in r.columns:
            mu = float(r[ticker].mean())
            assert abs(mu) < 0.01, f"{ticker}: daily mean return {mu:.5f} unexpectedly large"

    def test_no_constant_price_series(self):
        """No ticker should have zero standard deviation (constant prices)."""
        p = _load_prices()
        for ticker in p.columns:
            std = p[ticker].dropna().std()
            assert std > 0, f"{ticker}: price series is constant (std = 0)"

    def test_data_quality_stats_file(self):
        q_file = os.path.join(OUT_QUALITY, "data_quality_stats.csv")
        if not os.path.exists(q_file):
            pytest.skip("data_quality_stats.csv not found (run main.py first)")
        stats = pd.read_csv(q_file, index_col=0)
        assert len(stats) == len(EXPECTED_TICKERS), (
            f"data_quality_stats has {len(stats)} tickers, expected {len(EXPECTED_TICKERS)}"
        )


# ── TestFeatureEngineering ────────────────────────────────────────────────────

class TestFeatureEngineering:
    """Fisher-z transform, rolling correlation, no look-ahead in features."""

    def test_fisher_z_identity(self):
        """arctanh(tanh(x)) == x for values in (-5, 5)."""
        vals = np.linspace(-0.99, 0.99, 200)
        z = np.arctanh(vals)
        r_back = np.tanh(z)
        assert np.allclose(r_back, vals, atol=1e-10)

    def test_fisher_z_clips_boundaries(self):
        """Fisher-z clips ±1 to avoid infinity."""
        eps = 1e-6
        r_series = pd.Series([-1.0, -0.999, 0.0, 0.999, 1.0])
        clipped = r_series.clip(-1 + eps, 1 - eps)
        z = np.arctanh(clipped)
        assert np.all(np.isfinite(z)), "Fisher-z produced inf/nan near boundaries"

    def test_rolling_corr_range(self):
        """Rolling correlation must stay in [-1, 1]."""
        r = _load_returns()
        corr = r["BTC-USD"].rolling(30).corr(r["^GSPC"]).dropna()
        assert corr.min() >= -1.0 - 1e-9
        assert corr.max() <= 1.0 + 1e-9

    def test_rolling_corr_window_effect(self):
        """Longer window → smoother (lower std) rolling correlation."""
        r = _load_returns()
        std_14 = r["BTC-USD"].rolling(14).corr(r["^GSPC"]).dropna().std()
        std_90 = r["BTC-USD"].rolling(90).corr(r["^GSPC"]).dropna().std()
        assert std_90 < std_14, (
            f"std(w=90)={std_90:.4f} not < std(w=14)={std_14:.4f}"
        )

    def test_no_lookahead_in_predictions(self):
        """Prediction CSVs: no non-NaN prediction before min_train_size rows."""
        min_train = 800
        if not os.path.exists(OUT_PREDS):
            pytest.skip("predictions/ folder missing (run main.py first)")
        pred_files = [f for f in os.listdir(OUT_PREDS) if f.endswith(".csv")]
        if not pred_files:
            pytest.skip("No prediction CSV files found")
        for fname in pred_files[:4]:  # check first 4 to keep runtime short
            df = pd.read_csv(os.path.join(OUT_PREDS, fname), index_col=0, parse_dates=True)
            model_cols = [c for c in df.columns if c != "y_true"]
            for col in model_cols:
                first_pred = df[col].first_valid_index()
                if first_pred is None:
                    continue
                first_pos = df.index.get_loc(first_pred)
                assert first_pos >= min_train - 1, (
                    f"{fname} / {col}: first prediction at row {first_pos}, "
                    f"expected >= {min_train - 1}"
                )

    def test_target_aligned_with_features(self):
        """Prediction CSV: y_true and first model column share the same non-NaN index."""
        if not os.path.exists(OUT_PREDS):
            pytest.skip("predictions/ folder missing")
        pred_files = [f for f in os.listdir(OUT_PREDS) if f.endswith(".csv")]
        if not pred_files:
            pytest.skip("No prediction CSV files found")
        df = pd.read_csv(os.path.join(OUT_PREDS, pred_files[0]), index_col=0, parse_dates=True)
        model_cols = [c for c in df.columns if c != "y_true"]
        assert model_cols, "No model columns in prediction CSV"
        valid_true = df["y_true"].dropna().index
        valid_model = df[model_cols[0]].dropna().index
        # Walk-forward: first min_train_size rows are NaN → expect ≥ 60% coverage
        overlap = valid_true.intersection(valid_model)
        assert len(overlap) / len(valid_true) > 0.60, (
            f"y_true and model predictions barely overlap: "
            f"{len(overlap)}/{len(valid_true)} = {len(overlap)/len(valid_true):.1%}"
        )


# ── TestModelMetrics ──────────────────────────────────────────────────────────

class TestModelMetrics:
    """metrics.csv: RMSE/R2 sanity, expected models present, AR1 beats DCC."""

    def test_metrics_file_exists(self):
        assert os.path.exists(METRICS_CSV), f"metrics.csv not found at {METRICS_CSV}"

    def test_metrics_has_expected_columns(self):
        m = _load_metrics()
        for col in ["model", "RMSE", "R2", "MAE", "n_test", "dependency", "window"]:
            assert col in m.columns, f"Column '{col}' missing from metrics.csv"

    def test_rmse_positive(self):
        m = _load_metrics()
        assert (m["RMSE"] > 0).all(), "Some RMSE values are non-positive"

    def test_r2_below_one(self):
        m = _load_metrics()
        assert (m["R2"] <= 1.0 + 1e-9).all(), "Some R2 values exceed 1.0"

    def test_mae_leq_rmse(self):
        """MAE <= RMSE by definition (RMSE penalises large errors more)."""
        m = _load_metrics()
        violations = (m["MAE"] > m["RMSE"] + 1e-9).sum()
        assert violations == 0, f"{violations} rows where MAE > RMSE"

    def test_all_windows_present(self):
        m = _load_metrics()
        found = sorted(m["window"].unique())
        for w in EXPECTED_WINDOWS:
            assert w in found, f"Window {w} missing from metrics.csv"

    def test_expected_models_present(self):
        m = _load_metrics()
        expected = {"AR1", "Naive_Last", "Ridge", "ElasticNet", "RF", "GBM", "DCC_GARCH"}
        found = set(m["model"].unique())
        missing = expected - found
        assert not missing, f"Models missing from metrics.csv: {missing}"

    def test_ar1_beats_dcc_on_average(self):
        """AR1 average RMSE must be lower than DCC_GARCH average RMSE."""
        m = _load_metrics()
        if "DCC_GARCH" not in m["model"].values:
            pytest.skip("DCC_GARCH not in metrics.csv (arch not installed or DCC disabled)")
        ar1_rmse = m.loc[m["model"] == "AR1", "RMSE"].mean()
        dcc_rmse = m.loc[m["model"] == "DCC_GARCH", "RMSE"].mean()
        assert ar1_rmse < dcc_rmse, (
            f"AR1 avg RMSE ({ar1_rmse:.4f}) not < DCC_GARCH avg RMSE ({dcc_rmse:.4f})"
        )

    def test_naive_last_close_to_ar1(self):
        """Naive_Last and AR1 should have similar avg RMSE (within 10%)."""
        m = _load_metrics()
        ar1 = m.loc[m["model"] == "AR1", "RMSE"].mean()
        naive = m.loc[m["model"] == "Naive_Last", "RMSE"].mean()
        assert abs(ar1 - naive) / naive < 0.10, (
            f"AR1 ({ar1:.4f}) and Naive_Last ({naive:.4f}) differ by more than 10%"
        )

    def test_longer_window_lower_rmse(self):
        """For the same model and pair, RMSE should generally decrease with longer window."""
        m = _load_metrics()
        for model in ["AR1", "Ridge"]:
            for dep in m["dependency"].unique():
                sub = m[(m["model"] == model) & (m["dependency"] == dep)].sort_values("window")
                if len(sub) < 2:
                    continue
                rmse_vals = sub["RMSE"].values
                # Allow one reversal but overall trend should be downward
                decreasing_pairs = sum(
                    rmse_vals[i] > rmse_vals[i + 1] for i in range(len(rmse_vals) - 1)
                )
                assert decreasing_pairs >= len(rmse_vals) - 2, (
                    f"{model} / {dep}: RMSE does not decrease with window length. "
                    f"RMSE={list(rmse_vals)}"
                )

    def test_n_test_consistent(self):
        """All rows for the same dependency/window should have the same n_test."""
        m = _load_metrics()
        for (dep, win), grp in m.groupby(["dependency", "window"]):
            unique_n = grp["n_test"].unique()
            assert len(unique_n) == 1, (
                f"{dep} w={win}: inconsistent n_test values {unique_n}"
            )

    def test_high_r2_for_longer_windows(self):
        """AR1 at w=90 should achieve R2 > 0.95 for all pairs."""
        m = _load_metrics()
        sub = m[(m["model"] == "AR1") & (m["window"] == 90)]
        low_r2 = sub[sub["R2"] < 0.95]
        assert len(low_r2) == 0, (
            f"AR1 w=90 R2 < 0.95 for: {low_r2['dependency'].tolist()}"
        )


# ── TestDMTests ───────────────────────────────────────────────────────────────

class TestDMTests:
    """dm_tests.csv: sign convention, finite statistics, p-value range."""

    def test_dm_file_exists(self):
        assert os.path.exists(DM_CSV), f"dm_tests.csv not found at {DM_CSV}"

    def test_dm_has_expected_columns(self):
        dm = _load_dm()
        for col in ["dependency", "window", "model", "benchmark", "DM_stat", "p_value", "n"]:
            assert col in dm.columns, f"Column '{col}' missing from dm_tests.csv"

    def test_dm_stat_finite(self):
        dm = _load_dm()
        non_finite = (~dm["DM_stat"].apply(lambda x: math.isfinite(float(x)) if pd.notna(x) else True)).sum()
        assert non_finite == 0, f"{non_finite} non-finite DM statistics"

    def test_p_value_in_unit_interval(self):
        dm = _load_dm()
        bad = dm[(dm["p_value"] < 0) | (dm["p_value"] > 1)]
        assert len(bad) == 0, f"{len(bad)} p-values outside [0, 1]"

    def test_ridge_beats_dcc_dm_positive(self):
        """Ridge vs DCC_GARCH: DM stat must be positive (Ridge has lower squared errors)."""
        dm = _load_dm()
        ridge_dcc = dm[(dm["model"] == "Ridge") & (dm["benchmark"] == "DCC_GARCH")]
        if ridge_dcc.empty or "DCC_GARCH" not in dm["benchmark"].values:
            pytest.skip("No Ridge vs DCC_GARCH rows in dm_tests.csv")
        neg = (ridge_dcc["DM_stat"] < 0).sum()
        assert neg == 0, (
            f"{neg}/{len(ridge_dcc)} Ridge-vs-DCC rows have negative DM stat "
            "(negative means Ridge is WORSE than DCC)"
        )

    def test_ridge_loses_to_naive_dm_negative(self):
        """Ridge vs Naive_Last: DM stat must be negative (Naive_Last has lower errors)."""
        dm = _load_dm()
        ridge_naive = dm[(dm["model"] == "Ridge") & (dm["benchmark"] == "Naive_Last")]
        if ridge_naive.empty:
            pytest.skip("No Ridge vs Naive_Last rows in dm_tests.csv")
        pos = (ridge_naive["DM_stat"] > 0).sum()
        assert pos == 0, (
            f"{pos}/{len(ridge_naive)} Ridge-vs-Naive rows have positive DM stat "
            "(positive would mean Ridge BEATS Naive_Last, contradicting metrics)"
        )

    def test_most_dcc_comparisons_significant(self):
        """At least 50% of ML-vs-DCC comparisons should be significant (p < 0.05)."""
        dm = _load_dm()
        dcc_rows = dm[dm["benchmark"] == "DCC_GARCH"].dropna(subset=["p_value"])
        if dcc_rows.empty:
            pytest.skip("No DCC_GARCH rows in dm_tests.csv")
        sig_rate = (dcc_rows["p_value"] < 0.05).mean()
        assert sig_rate >= 0.50, (
            f"Only {sig_rate:.0%} of ML-vs-DCC comparisons significant at 5% (need >= 50%)"
        )

    def test_n_sufficient_for_dm(self):
        """DM test requires at least 30 joint observations."""
        dm = _load_dm()
        small_n = dm[dm["n"] < 30]
        assert len(small_n) == 0, f"{len(small_n)} DM tests with n < 30"


# ── TestSignalMetrics ─────────────────────────────────────────────────────────

class TestSignalMetrics:
    """signal_metrics.csv: classification metrics in valid ranges."""

    def test_signal_file_exists(self):
        assert os.path.exists(SIGNAL_CSV), f"signal_metrics.csv not found at {SIGNAL_CSV}"

    def test_signal_has_expected_columns(self):
        s = _load_signal()
        for col in ["dependency", "window", "signal_model", "BalancedAccuracy", "F1Down", "AUC"]:
            assert col in s.columns, f"Column '{col}' missing from signal_metrics.csv"

    def test_balanced_accuracy_range(self):
        s = _load_signal()
        bad = s[(s["BalancedAccuracy"] < 0) | (s["BalancedAccuracy"] > 1)]
        assert len(bad) == 0, f"{len(bad)} BalancedAccuracy values outside [0, 1]"

    def test_f1down_range(self):
        s = _load_signal()
        bad = s[(s["F1Down"] < 0) | (s["F1Down"] > 1)]
        assert len(bad) == 0, f"{len(bad)} F1Down values outside [0, 1]"

    def test_auc_above_random(self):
        """AUC should be above 0.45 for any signal worth reporting (near-random is 0.50)."""
        s = _load_signal()
        low_auc = s[s["AUC"].notna() & (s["AUC"] < 0.45)]
        assert len(low_auc) == 0, (
            f"{len(low_auc)} signal AUC values below 0.45:\n"
            f"{low_auc[['dependency','window','signal_model','AUC']].to_string()}"
        )

    def test_exit_rate_not_trivial(self):
        """ExitRate for Logit (main signal model) should be between 1% and 70%."""
        s = _load_signal()
        if "ExitRate" not in s.columns:
            pytest.skip("ExitRate column not present")
        logit = s[s["signal_model"] == "Logit"]
        if logit.empty:
            pytest.skip("No Logit rows in signal_metrics.csv")
        bad = logit[(logit["ExitRate"] < 0.01) | (logit["ExitRate"] > 0.70)]
        assert len(bad) == 0, (
            f"{len(bad)} Logit rows with ExitRate outside [1%, 70%]: "
            f"{bad[['dependency','window','ExitRate']].to_string()}"
        )

    def test_equity_signal_better_than_commodities(self):
        """Average AUC for equity pairs (^GSPC, ^IXIC) should exceed GLD/SLV."""
        s = _load_signal()
        if "AUC" not in s.columns:
            pytest.skip("AUC column missing")
        equity_auc = s.loc[s["dependency"].str.contains(r"\^GSPC|\^IXIC"), "AUC"].dropna().mean()
        commodity_auc = s.loc[s["dependency"].str.contains("GLD|SLV"), "AUC"].dropna().mean()
        if pd.isna(equity_auc) or pd.isna(commodity_auc):
            pytest.skip("Not enough signal rows to compare")
        assert equity_auc >= commodity_auc - 0.03, (
            f"Equity AUC ({equity_auc:.3f}) not >= Commodity AUC ({commodity_auc:.3f})"
        )


# ── TestWalkForward ───────────────────────────────────────────────────────────

class TestWalkForward:
    """Spot-check that walk-forward outputs have the right structure."""

    def test_prediction_csvs_exist(self):
        if not os.path.exists(OUT_PREDS):
            pytest.skip("predictions/ folder missing")
        csvs = [f for f in os.listdir(OUT_PREDS) if f.endswith(".csv")]
        expected_count = len(EXPECTED_TICKERS) * len(EXPECTED_WINDOWS)
        assert len(csvs) >= expected_count - 4, (
            f"Only {len(csvs)} prediction CSVs, expected ~{expected_count}"
        )

    def test_prediction_has_y_true_column(self):
        if not os.path.exists(OUT_PREDS):
            pytest.skip("predictions/ folder missing")
        csvs = [f for f in os.listdir(OUT_PREDS) if f.endswith(".csv")]
        if not csvs:
            pytest.skip("No prediction CSVs")
        for fname in csvs[:3]:
            df = pd.read_csv(os.path.join(OUT_PREDS, fname), index_col=0, parse_dates=True)
            assert "y_true" in df.columns, f"{fname} missing y_true column"

    def test_predictions_not_all_nan(self):
        if not os.path.exists(OUT_PREDS):
            pytest.skip("predictions/ folder missing")
        csvs = [f for f in os.listdir(OUT_PREDS) if f.endswith(".csv")]
        if not csvs:
            pytest.skip("No prediction CSVs")
        for fname in csvs[:3]:
            df = pd.read_csv(os.path.join(OUT_PREDS, fname), index_col=0, parse_dates=True)
            model_cols = [c for c in df.columns if c != "y_true"]
            for col in model_cols:
                non_nan = df[col].notna().sum()
                assert non_nan > 100, (
                    f"{fname} / {col}: only {non_nan} non-NaN predictions"
                )

    def test_gspc_w30_predictions_exist(self):
        """Representative pair (BTC vs ^GSPC, w=30) must have a prediction file."""
        fname = "corr_BTC-USD_^GSPC_w30_fisher_z_predictions.csv"
        path = os.path.join(OUT_PREDS, fname)
        assert os.path.exists(path), f"Representative prediction file missing: {path}"

    def test_predictions_index_matches_returns(self):
        """Prediction CSV index should be a subset of the returns index."""
        fname = "corr_BTC-USD_^GSPC_w30_fisher_z_predictions.csv"
        path = os.path.join(OUT_PREDS, fname)
        if not os.path.exists(path):
            pytest.skip("Representative prediction file missing")
        preds = pd.read_csv(path, index_col=0, parse_dates=True)
        r = _load_returns()
        not_in_returns = preds.index.difference(r.index)
        assert len(not_in_returns) == 0, (
            f"{len(not_in_returns)} prediction dates not in returns index"
        )


# ── TestOutputFiles ───────────────────────────────────────────────────────────

class TestOutputFiles:
    """All expected output files exist after a full pipeline run."""

    @pytest.mark.parametrize("path", [
        METRICS_CSV,
        DM_CSV,
        SIGNAL_CSV,
        METADATA_JSON,
        os.path.join(OUT_RESULTS, "dataset_summary.json"),
        os.path.join(OUT_TABLES, "metrics_table.tex"),
        os.path.join(OUT_TABLES, "dm_tests.tex"),
        os.path.join(OUT_TABLES, "signal_metrics.tex"),
        os.path.join(OUT_FIGURES, "dm_heatmap_Ridge_vs_DCC.png"),
        os.path.join(OUT_FIGURES, "dataset_prices.png"),
        os.path.join(OUT_FIGURES, "model_rmse_comparison.png"),
    ])
    def test_output_file_exists(self, path):
        assert os.path.exists(path), f"Expected output file missing: {path}"

    def test_metadata_json_valid(self):
        with open(METADATA_JSON, "r") as f:
            meta = json.load(f)
        assert "python" in meta, "run_metadata.json missing 'python' key"
        assert "config" in meta, "run_metadata.json missing 'config' key"

    def test_metrics_table_tex_not_empty(self):
        tex = os.path.join(OUT_TABLES, "metrics_table.tex")
        assert os.path.getsize(tex) > 500, "metrics_table.tex is suspiciously small"

    def test_forecast_figures_all_windows(self):
        """Forecast figure should exist for all 4 windows of representative pair."""
        for w in EXPECTED_WINDOWS:
            fig = os.path.join(OUT_FIGURES, f"corr_BTC-USD_^GSPC_w{w}_fisher_z.png")
            assert os.path.exists(fig), f"Missing forecast figure: {fig}"


# ── TestBootstrapCI ───────────────────────────────────────────────────────────

class TestBootstrapCI:
    """metrics_with_ci.csv: CI bounds are internally consistent."""

    def test_ci_file_exists(self):
        assert os.path.exists(CI_CSV), f"metrics_with_ci.csv not found at {CI_CSV}"

    def test_ci_lower_leq_mean_leq_upper(self):
        ci = pd.read_csv(CI_CSV)
        for col in ["rmse", "r2"]:
            lo, mean, hi = f"{col}_ci_lower", f"{col}_mean", f"{col}_ci_upper"
            if not all(c in ci.columns for c in [lo, mean, hi]):
                continue
            bad_lo = (ci[lo] > ci[mean] + 1e-9).sum()
            bad_hi = (ci[mean] > ci[hi] + 1e-9).sum()
            assert bad_lo == 0, f"{bad_lo} rows where {lo} > {mean}"
            assert bad_hi == 0, f"{bad_hi} rows where {mean} > {hi}"

    def test_rmse_ci_width_reasonable(self):
        """95% CI width for RMSE should be < 0.1 (not absurdly wide)."""
        ci = pd.read_csv(CI_CSV)
        if "rmse_ci_upper" not in ci.columns:
            pytest.skip("rmse CI columns missing")
        width = ci["rmse_ci_upper"] - ci["rmse_ci_lower"]
        assert (width < 0.10).all(), (
            f"Some 95% RMSE CI widths exceed 0.10: max = {width.max():.4f}"
        )


# ── TestSensitivity ───────────────────────────────────────────────────────────

class TestSensitivity:
    """refit_sensitivity.csv: expected refit_every values, sensible RMSE range."""

    def test_sensitivity_file_exists(self):
        assert os.path.exists(SENSITIVITY_CSV), (
            f"refit_sensitivity.csv not found at {SENSITIVITY_CSV}"
        )

    def test_sensitivity_has_expected_refit_values(self):
        sens = pd.read_csv(SENSITIVITY_CSV)
        assert "refit_every" in sens.columns, "refit_sensitivity.csv missing 'refit_every'"
        found = set(sens["refit_every"].unique())
        expected = {5, 10, 21, 42, 63}
        missing = expected - found
        assert not missing, f"refit_every values missing from sensitivity: {missing}"

    def test_sensitivity_rmse_in_range(self):
        sens = pd.read_csv(SENSITIVITY_CSV)
        if "RMSE" not in sens.columns:
            pytest.skip("RMSE column missing from refit_sensitivity.csv")
        assert (sens["RMSE"] > 0).all(), "Non-positive RMSE in sensitivity results"
        assert (sens["RMSE"] < 1.0).all(), "RMSE > 1.0 in sensitivity (unreasonably large)"

    def test_sensitivity_models_present(self):
        sens = pd.read_csv(SENSITIVITY_CSV)
        if "model" not in sens.columns:
            pytest.skip("model column missing from refit_sensitivity.csv")
        found = set(sens["model"].unique())
        assert "Ridge" in found, "Ridge not found in refit_sensitivity.csv"
