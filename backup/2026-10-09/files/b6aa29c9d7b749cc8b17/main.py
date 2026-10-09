"""
Intermarket Dependency Forecasting — D:/clode9
Entry point: runs the full pipeline (data download → models → metrics → DM tests → figures).
"""
from thesis_app.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline(config_path="config.yaml")
#D:\clode9\
#├── main.py                 ← запускать первым
#├── config.yaml             ← все настройки
#├── requirements.txt
#├── thesis_app\
#│   ├── pipeline.py         ← весь пайплайн (улучшенный)
#│   └── dcc.py              ← DCC-GARCH (улучшенный)
#└── notebooks\
#    ├── 01_EDA_Dataset.ipynb
#    ├── 02_GridSearch.ipynb
#    ├── 03_Model_Comparison.ipynb
#    ├── 04_DM_Tests_Visuals.ipynb
#    └── 05_XGB_vs_DCC.ipynb