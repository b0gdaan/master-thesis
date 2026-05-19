# Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning

**Master's Thesis — Bogdan Babaev**
Faculty of Engineering Sciences, University of Kragujevac, Serbia (2023–2026)

---

## Overview

This project investigates whether cryptocurrency market dynamics can be used to forecast
time-varying dependency structures between Bitcoin and conventional financial assets —
equity indices, precious-metal ETFs, and the U.S. dollar index.

A fully reproducible machine-learning pipeline is developed covering:
data acquisition, return construction, rolling-correlation target generation,
feature engineering, walk-forward model evaluation, and benchmarking against
a leakage-safe DCC-GARCH(1,1) specification.

**Key finding:** Intermarket dependency is forecastable, with most predictive power
originating from persistence in the dependency series itself. ML models provide
meaningful improvements over the DCC-GARCH econometric benchmark.

---

## Asset Universe

| Symbol | Asset | Type |
|--------|-------|------|
| BTC-USD | Bitcoin | Crypto (base) |
| ETH-USD | Ethereum | Crypto (reference) |
| ^GSPC | S&P 500 | Equity index |
| ^IXIC | NASDAQ Composite | Equity index |
| GLD | SPDR Gold Shares ETF | Precious metal |
| SLV | iShares Silver Trust ETF | Precious metal |
| UUP | Invesco US Dollar Index | Currency |

Daily prices 2017–2026 · source: Yahoo Finance

---

## Methodology

- **Target**: rolling Pearson correlation (BTC vs each asset) — windows: 14 / 30 / 60 / 90 days
- **Transform**: Fisher-z (arctanh) for variance stabilization
- **Features**: momentum, volatility, return-based predictors derived from the dependency series
- **Models**: AR(1), ElasticNet, Ridge, Random Forest, GBM, XGBoost vs DCC-GARCH(1,1) benchmark
- **Evaluation**: walk-forward expanding window (no data leakage)
- **Statistical tests**: Diebold-Mariano with Newey-West correction
- **Signal layer**: logistic classifier for investor stress-day detection on traditional assets

---

## Project Structure

```
├── main.py                  # Entry point — runs full pipeline
├── run_all.py               # Full reproducibility runner (pipeline + notebooks)
├── config.yaml              # All settings
├── requirements.txt
│
├── thesis_app/
│   ├── pipeline.py          # Core ML pipeline
│   ├── dcc.py               # DCC-GARCH(1,1) benchmark
│   ├── dcc_walk.py          # Walk-forward DCC wrapper
│   ├── signal_layer.py      # Investor signal layer
│   ├── regime_analysis.py   # Regime detection utilities
│   ├── data_quality.py      # Data validation
│   └── notebook_helpers.py  # Shared notebook utilities
│
├── notebooks/
│   ├── 01_EDA_Dataset.ipynb        # Exploratory data analysis
│   ├── 02_GridSearch.ipynb         # Hyperparameter search (TimeSeriesSplit)
│   ├── 03_Model_Comparison.ipynb   # RMSE/R² across all pairs & windows
│   ├── 04_DM_Tests_Visuals.ipynb   # Diebold-Mariano tests & thesis figures
│   ├── 05_XGB_vs_DCC.ipynb         # XGBoost vs DCC-GARCH deep dive
│   ├── 06_Regime_Analysis.ipynb    # Dependency regime analysis
│   └── 07_Robustness_Checks.ipynb  # Sensitivity & robustness
│
├── data/                    # Auto-created on first run
├── outputs/                 # Auto-created: figures, results, predictions
└── models/                  # Auto-created: saved model artefacts
```

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/b0gdaan/master-thesis.git
cd master-thesis

# 2. Create virtual environment (Python 3.14 recommended)
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate   # Linux / macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run full pipeline
python main.py
```

First run downloads ~10 years of price data from Yahoo Finance (~30 sec).
Subsequent runs use the cached CSV in `data/raw/`.

**No GPU?** Set `xgb_device: "cpu"` in `config.yaml`.
**No DCC-GARCH?** Set `use_dcc_garch: false` in `config.yaml`.

---

## Notebooks

Run after `main.py` (outputs must exist):

```bash
jupyter notebook
```

| Notebook | Purpose |
|----------|---------|
| `01_EDA_Dataset.ipynb` | Price/return EDA, ADF stationarity tests, correlation overview |
| `02_GridSearch.ipynb` | Hyperparameter tuning with TimeSeriesSplit CV |
| `03_Model_Comparison.ipynb` | RMSE / R² heatmaps, model ranking, LaTeX tables |
| `04_DM_Tests_Visuals.ipynb` | DM significance tests, publication-quality forecast plots |
| `05_XGB_vs_DCC.ipynb` | Error analysis, rolling RMSE, scatter diagnostics |
| `06_Regime_Analysis.ipynb` | Dependency regime detection and characterization |
| `07_Robustness_Checks.ipynb` | Sensitivity to rolling window length and refit frequency |

---

## Configuration

All parameters are in `config.yaml`:

| Key | Default | Description |
|-----|---------|-------------|
| `base_asset` | `BTC-USD` | Base cryptocurrency |
| `rolling_windows` | `[14,30,60,90]` | Correlation window sizes (days) |
| `use_fisher_transform` | `true` | Fisher-z transform on correlation target |
| `use_dcc_garch` | `true` | Include DCC-GARCH(1,1) benchmark |
| `use_xgboost` | `true` | Include XGBoost model |
| `xgb_device` | `cuda` | `cuda` for GPU, `cpu` for CPU |
| `min_train_size` | `800` | Minimum training observations (walk-forward) |
| `refit_every` | `20` | Model refit frequency (trading days) |
| `enable_signal_layer` | `true` | Run investor stress-warning signal layer |

---

## Tech Stack

Python 3.14 · pandas 3.0 · numpy 2.4 · scikit-learn 1.8 · XGBoost 3.2 · arch 8.0 · scipy 1.17 · yfinance 1.2 · matplotlib · seaborn · Jupyter

---

## Author

**Bogdan Babaev**
M.Sc. Artificial Intelligence — University of Kragujevac, Serbia
[github.com/b0gdaan](https://github.com/b0gdaan) · [linkedin.com/in/b0gdaan](https://www.linkedin.com/in/b0gdaan/)