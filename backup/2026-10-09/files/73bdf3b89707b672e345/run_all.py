"""
Full reproducibility runner: pipeline → notebooks → LaTeX PDF

Usage:
    python run_all.py
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
THESIS_DIR = os.path.join(BASE, "thesis")
NOTEBOOKS_DIR = os.path.join(BASE, "notebooks")
PYTHON = sys.executable

NOTEBOOKS = [
    "01_EDA_Dataset.ipynb",
    "02_GridSearch.ipynb",
    "03_Model_Comparison.ipynb",
    "04_DM_Tests_Visuals.ipynb",
    "05_XGB_vs_DCC.ipynb",
    "06_Regime_Analysis.ipynb",
]


def _run(cmd, cwd=None, label=""):
    label = label or " ".join(str(x) for x in cmd)
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"ERROR: exited with code {result.returncode}")
        sys.exit(result.returncode)


def step_pipeline():
    _run([PYTHON, os.path.join(BASE, "main.py")], label="STEP 1: pipeline (main.py)")


def step_notebooks():
    for nb in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOKS_DIR, nb)
        if not os.path.exists(nb_path):
            print(f"  Skipping {nb}: not found")
            continue
        _run(
            [
                PYTHON, "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=1200",
                "--ExecutePreprocessor.kernel_name=python3",
                nb_path,
            ],
            label=f"STEP 2: notebook {nb}",
        )


def step_latex():
    has_latexmk = subprocess.run(
        ["latexmk", "--version"], capture_output=True
    ).returncode == 0

    if has_latexmk:
        _run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=THESIS_DIR,
            label="STEP 3: latexmk",
        )
    else:
        for i in range(2):
            _run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=THESIS_DIR,
                label=f"STEP 3: pdflatex pass {i + 1}",
            )
        r = subprocess.run(["biber", "main"], cwd=THESIS_DIR, capture_output=True)
        if r.returncode != 0:
            _run(["bibtex", "main"], cwd=THESIS_DIR, label="STEP 3: bibtex")
        else:
            print("biber complete")
        for i in range(2):
            _run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=THESIS_DIR,
                label=f"STEP 3: pdflatex pass {i + 3}",
            )

    pdf = os.path.join(THESIS_DIR, "main.pdf")
    if os.path.exists(pdf):
        print(f"\nPDF ready: {pdf}")
    else:
        print("\nWARNING: main.pdf not found after compilation.")


if __name__ == "__main__":
    step_pipeline()
    step_notebooks()
    step_latex()
    print("\nAll steps complete.")
