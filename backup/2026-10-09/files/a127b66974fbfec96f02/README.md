# Intermarket Dependency Forecasting — D:/clode9

Master Thesis Project: **Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning**

---

## Project Structure

```
D:\clode9\
├── main.py                        # Entry point — run this first
├── config.yaml                    # All settings
├── requirements.txt
│
├── thesis_app\
│   ├── __init__.py
│   ├── pipeline.py                # Core pipeline (data → models → metrics → DM tests)
│   └── dcc.py                     # DCC-GARCH(1,1) econometric benchmark
│
├── notebooks\
│   ├── 01_EDA_Dataset.ipynb       # Exploratory data analysis
│   ├── 02_GridSearch.ipynb        # Hyperparameter optimization (TimeSeriesSplit)
│   ├── 03_Model_Comparison.ipynb  # Compare all models across pairs & windows
│   ├── 04_DM_Tests_Visuals.ipynb  # Diebold–Mariano tests & thesis figures
│   └── 05_XGB_vs_DCC.ipynb        # Deep dive: XGB vs DCC-GARCH
│
├── data\
│   ├── raw\prices.csv             # (auto-created on first run)
│   └── processed\returns.csv     # (auto-created on first run)
│
└── outputs\
    ├── figures\                   # All plots (PNG, 130 dpi)
    ├── predictions\               # Per-experiment forecast CSVs
    │   └── corr_BTC-USD_^GSPC_w30_fisher_z_predictions.csv
    ├── results\
    │   ├── metrics.csv            # MAE / RMSE / R² per model
    │   ├── dm_tests.csv           # Diebold–Mariano test results
    │   └── run_metadata.json
    ├── tables\
    │   ├── metrics_table.tex      # LaTeX table for thesis
    │   └── dm_tests.tex
    └── models\
```

---

## Setup

```bash
# 1. Create venv (Python 3.11 recommended)
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Run

```bash
# Full pipeline (data download → all models → metrics → DM tests → figures)
python main.py
```

**First run**: downloads ~10 years of price data from Yahoo Finance (~30 sec).  
**Subsequent runs**: uses cached CSV. To force re-download, delete `data/raw/prices.csv`.

---

## Notebooks (run after main.py)

| Notebook | Purpose |
|---|---|
| `01_EDA_Dataset.ipynb` | Price/return analysis, ADF tests, Fisher-z illustration |
| `02_GridSearch.ipynb` | Hyperparameter tuning with TimeSeriesSplit CV |
| `03_Model_Comparison.ipynb` | RMSE/R² heatmaps, ranking, LaTeX table |
| `04_DM_Tests_Visuals.ipynb` | DM tests, publication-quality forecast plots |
| `05_XGB_vs_DCC.ipynb` | Error analysis, rolling RMSE, scatter plots |

Launch Jupyter:
```bash
jupyter notebook --notebook-dir="D:\clode9\notebooks"
```

---

## Configuration (`config.yaml`)

| Key | Default | Description |
|---|---|---|
| `base_asset` | `BTC-USD` | Base cryptocurrency |
| `rolling_windows` | `[14,30,60,90]` | Correlation window sizes |
| `use_fisher_transform` | `true` | Fisher-z transform on target |
| `use_dcc_garch` | `true` | Include DCC-GARCH benchmark |
| `use_xgboost` | `true` | Include XGBoost model |
| `xgb_device` | `cuda` | GPU (`cuda`) or CPU (`cpu`) |
| `min_train_size` | `800` | Minimum training obs (walk-forward) |
| `refit_every` | `20` | Refit frequency (days) |

### No GPU?
Set `xgb_device: "cpu"` in `config.yaml`.

### No `arch` package (DCC)?
Set `use_dcc_garch: false` in `config.yaml`.

---

## What gets forecasted

- **Target**: rolling Pearson correlation between `BTC-USD` and each asset
- **Transform**: Fisher-z (arctanh) for variance stabilization  
- **Horizon**: 1 step ahead
- **Models**: Naive, AR(1), ElasticNet, Ridge, RandomForest, GBM, XGBoost, DCC-GARCH
- **Pairs**: BTC vs S&P500, NASDAQ, GLD, SLV, UUP, ETH
- **Windows**: 14, 30, 60, 90 days

---

## Key outputs for thesis

- `outputs/results/metrics.csv` — main results table
- `outputs/results/dm_tests.csv` — statistical significance
- `outputs/tables/metrics_table.tex` — copy into LaTeX
- `outputs/tables/dm_tests.tex` — DM table for LaTeX
- `outputs/figures/` — all figures ready for thesis
