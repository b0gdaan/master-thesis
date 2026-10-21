# Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning

**Master's Thesis — Bogdan Babaev**
M.Sc. Artificial Intelligence · University of Kragujevac, Serbia (2023–2026)

---

## Overview

This project investigates whether cryptocurrency market dynamics can be used to forecast
time-varying dependency structures between Bitcoin and conventional financial assets —
equity indices, precious-metal ETFs, and the U.S. dollar index.

The research pipeline covers:
data acquisition, return construction, rolling-correlation target generation,
feature engineering, walk-forward model evaluation, and benchmarking against
a walk-forward DCC-GARCH(1,1) specification.

**Reported results:** Ridge, AR(1) and HAR form a close cluster by average RMSE
(0.0656–0.0659), versus 0.0666 for the last-value baseline. The last-value baseline
has the lowest average MAE (0.0395). Strong persistence in overlapping rolling
correlations explains much of the high R². DCC-GARCH has higher average RMSE
(0.2136), but forecasts conditional correlation rather than the same rolling
Pearson statistic. The stress classifier is near chance; the study does not
establish a profitable trading strategy.

Start with [the focused code repository](https://github.com/b0gdaan/master_rad)
for the pipeline, or `thesis/` here for the research text. Results above summarize
the committed thesis, not a newly reproduced experiment.

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

Configured download window: 2016-01-01 to 2026-05-17 · source: Yahoo Finance.
Effective samples depend on asset coverage, alignment and rolling-window warm-up.

---

## Methodology

- **Target**: rolling Pearson correlation (BTC vs each asset) — windows: 14 / 30 / 60 / 90 days
- **Transform**: Fisher-z (arctanh) for variance stabilization
- **Features**: momentum, volatility, return-based predictors derived from the dependency series
- **Models**: Naive_Last, AR(1), HAR, ElasticNet, Ridge, Adaptive Ensemble, Random Forest, GBM, XGBoost vs DCC-GARCH(1,1) benchmark (10 specifications total)
- **Evaluation**: walk-forward expanding window; preprocessing and feature availability must respect each forecast date
- **Statistical tests**: Diebold-Mariano with configurable variance lag (`dm_nw_lag`); the committed configuration uses lag 0, so serial dependence requires careful interpretation
- **Signal layer**: logistic classifier for investor stress-day detection on traditional assets

---

## Project Structure

```
├── main.py                  # Entry point — runs full pipeline
├── run_all.py               # Full reproducibility runner (pipeline + notebooks)
├── build_thesis.py          # Builds the thesis PDF (LaTeX only, no venv needed)
├── config.yaml              # All settings
├── requirements.txt
│
├── thesis/                  # LaTeX sources and the compiled PDF
│   ├── main.tex             # Title data, abstracts, document order
│   ├── chapters/            # Chapters 1–6 and Appendices A–F
│   ├── references.bib       # Bibliography (biber)
│   └── main.pdf             # Compiled thesis, 75 pages
│
├── website/                 # Project site (GitHub Pages)
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
│   ├── 07_Robustness_Checks.ipynb  # Sensitivity & robustness
│   └── 08_Market_Events_Showcase.ipynb  # Landmark market-event case studies
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

# 2. Create virtual environment (use a Python version compatible with requirements.txt)
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

## Building the thesis PDF

The compiled thesis is committed as `thesis/main.pdf`. To rebuild it, only a
LaTeX distribution is needed — the Python pipeline does not have to run, and no
virtual environment is required:

```bash
python build_thesis.py           # full build (~40 s)
python build_thesis.py --check   # verify toolchain and file dependencies only
```

The script reports page count, undefined references and overfull boxes; a clean
build is 75 pages with none of either. Setup instructions for a fresh machine
are in [BUILD.md](BUILD.md).

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
| `08_Market_Events_Showcase.ipynb` | Landmark market-event case studies (COVID, FTX, SVB, tariff shock, …) |

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
| `n_parallel_workers` | `8` | Parallel experiments (ThreadPoolExecutor) |
| `enable_signal_layer` | `true` | Run investor stress-warning signal layer |

---

## Tech Stack

Python 3.14 · pandas 3.0 · numpy 2.4 · scikit-learn 1.8 · XGBoost 3.2 · arch 8.0 · scipy 1.17 · yfinance 1.2 · matplotlib · seaborn · Jupyter

---

## Author

**Bogdan Babaev**
M.Sc. student · Artificial Intelligence — University of Kragujevac, Serbia (2023–2026)
[github.com/b0gdaan](https://github.com/b0gdaan) · [linkedin.com/in/b0gdaan](https://www.linkedin.com/in/b0gdaan/)
