"""
Intermarket Dependency Forecasting — entry point.

Runs the full pipeline:
  data download → feature engineering → walk-forward models
  → DCC-GARCH benchmark → metrics → DM tests → investor signal → figures

Usage
-----
    python main.py                    # uses config.yaml in the current directory
    python main.py path/to/config.yaml
"""
import sys
from thesis_app.pipeline import run_pipeline

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    try:
        run_pipeline(config_path=config_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}\nMake sure '{config_path}' exists.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        raise