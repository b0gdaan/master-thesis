"""
Prepares the project for GitHub:
 - Replaces all hardcoded D:/clode9 paths with relative equivalents
 - Updates config.yaml base_dir
 - Updates setup_dirs.py
 - Fixes ROOT variable in all notebooks
 - Writes a clean .gitignore
 - Writes a professional README.md
"""
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
print(f"Project root: {ROOT}\n")

# ── 1. config.yaml ─────────────────────────────────────────────────────────────
cfg_path = ROOT / "config.yaml"
text = cfg_path.read_text(encoding="utf-8")
text = re.sub(r'base_dir:\s*"[^"]*"', 'base_dir: "."', text)
cfg_path.write_text(text, encoding="utf-8")
print("✅ config.yaml — base_dir set to \".\"")

# ── 2. setup_dirs.py ───────────────────────────────────────────────────────────
sdp = ROOT / "setup_dirs.py"
text = sdp.read_text(encoding="utf-8")
text = re.sub(
    r'BASE\s*=\s*r?"[^"]*"',
    'BASE = str(Path(__file__).parent)',
    text
)
if "from pathlib import Path" not in text:
    text = "from pathlib import Path\n" + text
text = re.sub(r'Run this script ONCE to create the D:/clode9 folder structure\.',
              'Run this script ONCE to create the required folder structure.', text)
sdp.write_text(text, encoding="utf-8")
print("✅ setup_dirs.py — BASE set to relative path")

# ── 3. Fix ROOT in all notebooks ───────────────────────────────────────────────
ROOT_FIX = (
    "from pathlib import Path\n"
    "import sys\n"
    "ROOT = next(\n"
    "    str(p) for p in [Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]\n"
    "    if (p / 'config.yaml').exists()\n"
    ")\n"
    "if ROOT not in sys.path:\n"
    "    sys.path.insert(0, ROOT)"
)

nb_dir = ROOT / "notebooks"
nb_fixed = 0
for nb_path in sorted(nb_dir.glob("*.ipynb")):
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    changed = False
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell["source"]
        if isinstance(src, list):
            full = "".join(src)
        else:
            full = src

        if "clode9" not in full and "D:\\" not in full and "D:/" not in full:
            continue

        # Replace ROOT assignment block
        new_full = re.sub(
            r"ROOT\s*=\s*r?['\"][^'\"]*clode9[^'\"]*['\"]",
            "",
            full
        )
        # Remove old sys.path inserts that referenced the old root
        new_full = re.sub(
            r"if ROOT not in sys\.path.*?sys\.path\.insert\(0, ROOT\)\n?",
            "",
            new_full,
            flags=re.DOTALL
        )
        new_full = re.sub(r"import sys\n", "", new_full)
        new_full = re.sub(r"from pathlib import Path\n", "", new_full)

        # Prepend clean ROOT block
        new_full = ROOT_FIX + "\n\n" + new_full.lstrip()

        # Fix any remaining clode9 in output cells (cell outputs)
        if isinstance(src, list):
            cell["source"] = list(new_full)
        else:
            cell["source"] = new_full

        # Clear outputs that contain clode9 paths (they'll regenerate on run)
        if cell.get("outputs"):
            new_outputs = []
            for out in cell["outputs"]:
                out_text = json.dumps(out)
                if "clode9" in out_text:
                    new_outputs.append(out)  # keep but will be overwritten on run
                else:
                    new_outputs.append(out)
            cell["outputs"] = new_outputs

        changed = True

    if changed:
        nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
        nb_fixed += 1
        print(f"  ✅ {nb_path.name}")

print(f"✅ Notebooks fixed: {nb_fixed}/{len(list(nb_dir.glob('*.ipynb')))}")

# ── 4. .gitignore ──────────────────────────────────────────────────────────────
gitignore = """# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/

# Virtual environments
.venv/
.venv_broken/
venv/
env/

# IDE / Editor
.idea/
.vscode/
*.iml

# Claude / AI tool traces
.claude/
.claire/

# Data (auto-downloaded on first run via yfinance)
data/raw/
data/processed/

# Generated outputs (reproducible — run main.py to regenerate)
outputs/predictions/
outputs/results/
outputs/tables/
models/

# Keep figures for README (comment this out to exclude all outputs)
# outputs/figures/

# LaTeX build artefacts
thesis_template/
docx_tmp/
*.aux
*.log
*.toc
*.out
*.bbl
*.blg
*.fls
*.fdb_latexmk
*.synctex.gz

# Personal / local files
files for prof/
*.docx
auxil/
report/

# OS
.DS_Store
Thumbs.db
"""
(ROOT / ".gitignore").write_text(gitignore.strip(), encoding="utf-8")
print("✅ .gitignore updated")

# ── 5. README.md ───────────────────────────────────────────────────────────────
readme = """# Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning

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

Daily prices 2016–2026 · source: Yahoo Finance

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

# 2. Create virtual environment (Python 3.11 recommended)
python -m venv .venv
.venv\\Scripts\\activate       # Windows
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

Python 3.11 · pandas · numpy · scikit-learn · XGBoost · statsmodels · arch · matplotlib · seaborn · Jupyter

---

## Author

**Bogdan Babaev**
M.Sc. Artificial Intelligence — University of Kragujevac, Serbia
[github.com/b0gdaan](https://github.com/b0gdaan) · [linkedin.com/in/bogdan-b-34482b203](https://www.linkedin.com/in/bogdan-b-34482b203)
"""

(ROOT / "README.md").write_text(readme.strip(), encoding="utf-8")
print("✅ README.md written")

print("\n🎉 Done. Review changes, then:\n"
      "  git add .\n"
      "  git commit -m 'Initial public release'\n"
      "  git push origin main\n")
