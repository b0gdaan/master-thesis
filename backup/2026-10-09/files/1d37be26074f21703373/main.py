"""
Entry point: runs the full pipeline (data download → models → metrics → DM tests → figures).
"""
from thesis_app.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline(config_path="config.yaml")