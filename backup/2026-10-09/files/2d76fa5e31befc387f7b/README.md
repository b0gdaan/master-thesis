# Intermarket Dependency Forecasting (Master Thesis Project) — D:/progr (Windows, PyCharm)

This project forecasts **time-varying intermarket dependence** (rolling correlations) between **BTC** and conventional assets
(S&P 500, NASDAQ, GLD, SLV, UUP) using **walk-forward (expanding window) evaluation** and ML models.

It also includes **Variant A (econometric benchmark)**: **DCC-GARCH(1,1)**, plus thesis-friendly diagnostics and exports.

## 1) Environment (Python 3.11)
Create/activate your venv in PyCharm (Interpreter = Python 3.11) and install:

```bash
python -m pip install -r requirements.txt
```

If `arch` fails to install for any reason, you can temporarily set `use_dcc_garch: false` in `config.yaml`
(but for defense Variant A should be enabled).

## 2) Run
From `D:\progr`:

```bash
python main.py
```

## 3) Where the historical data is stored
After the first run, cached files appear here:

- `data/raw/prices.csv`  (Yahoo Finance adjusted prices)
- `data/processed/returns.csv` (log-returns)

## 4) Outputs created (for thesis)
- Figures: `outputs/figures/`
  - `dataset_prices.png`, `dataset_volatility.png`, `dataset_corr_heatmap.png`
  - `sensitivity_corr_<base>_<asset>.png`  (window sensitivity)
  - `corr_<base>_<asset>_w<window>_<space>.png`  (forecast plots)
- Results: `outputs/results/`
  - `metrics.csv` (MAE/RMSE/R2)
  - `dm_tests.csv` (Diebold–Mariano tests vs Naive and vs DCC)
  - `dataset_summary.json`, `run_metadata.json`
- LaTeX tables: `outputs/tables/`
  - `metrics_table.tex` (copy/include into your thesis)

## 5) Thesis notes
- Forecast target is in **Fisher-z space** (`use_fisher_transform: true`) which is recommended for correlations.
- Window sensitivity is enabled via `rolling_windows: [14,30,60,90]`.
- Yahoo access date is stored in config (`yahoo_access_date: "2026-01-01"`) for reproducibility.

