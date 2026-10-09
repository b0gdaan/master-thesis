"""
Full reproducibility runner: pipeline → notebooks → LaTeX PDF

Usage:
    python run_all.py                 # all steps
    python run_all.py --skip-latex    # skip LaTeX compilation
    python run_all.py --skip-notebooks
"""
import argparse
import importlib.metadata
import os
import subprocess
import sys
import time

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
    "07_Robustness_Checks.ipynb",
]

# Canonical package name → distribution name (for importlib.metadata lookup)
_PKG_MAP = {
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "xgboost": "xgboost",
    "arch": "arch",
    "statsmodels": "statsmodels",
    "seaborn": "seaborn",
    "nbconvert": "nbconvert",
    "nbformat": "nbformat",
}


def _preflight_check() -> None:
    """Verify installed package versions match requirements.txt.

    Reads the pinned versions from requirements.txt and compares them to
    what is installed.  Prints a one-line warning for each mismatch so the
    user can act before a 4-hour run starts.
    """
    req_file = os.path.join(BASE, "requirements.txt")
    if not os.path.exists(req_file):
        return

    mismatches = []
    with open(req_file) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "==" not in line:
                continue
            pkg_spec, required = line.split("==", 1)
            pkg_spec = pkg_spec.strip()
            required = required.strip()
            # Resolve distribution name
            dist_name = _PKG_MAP.get(pkg_spec.lower(), pkg_spec)
            try:
                installed = importlib.metadata.version(dist_name)
            except importlib.metadata.PackageNotFoundError:
                mismatches.append(f"  {pkg_spec}: MISSING (required {required})")
                continue
            if installed != required:
                mismatches.append(
                    f"  {pkg_spec}: installed {installed}, required {required}"
                )

    print(f"\n{'=' * 60}")
    print("PRE-FLIGHT: package version check")
    print(f"{'=' * 60}")
    if mismatches:
        print("WARNING — version mismatches detected:")
        for m in mismatches:
            print(m)
        print("\nRun:  pip install -r requirements.txt  to align versions.")
    else:
        print("OK — all packages match requirements.txt.")


def _run(cmd, cwd=None, label="", allow_failure: bool = False) -> bool:
    """Run a subprocess command, print a banner, and return True on success.

    Parameters
    ----------
    allow_failure : bool
        If True, a non-zero exit code prints a warning but does NOT abort.
    """
    label = label or " ".join(str(x) for x in cmd)
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd)
    elapsed = time.perf_counter() - t0
    if result.returncode != 0:
        msg = f"ERROR: '{label}' exited with code {result.returncode} ({elapsed:.1f}s)"
        if allow_failure:
            print(f"WARNING: {msg} — continuing.")
            return False
        print(msg)
        sys.exit(result.returncode)
    print(f"OK  ({elapsed:.1f}s)")
    return True


def step_pipeline():
    _run([PYTHON, os.path.join(BASE, "main.py")], label="STEP 1: pipeline (main.py)")


def step_notebooks():
    n_total = len(NOTEBOOKS)
    n_ok = 0
    for i, nb in enumerate(NOTEBOOKS, start=1):
        nb_path = os.path.join(NOTEBOOKS_DIR, nb)
        if not os.path.exists(nb_path):
            print(f"  [{i}/{n_total}] Skipping {nb}: not found")
            continue
        ok = _run(
            [
                PYTHON, "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=1200",
                "--ExecutePreprocessor.kernel_name=python3",
                f"--ExecutePreprocessor.cwd={BASE}",
                nb_path,
            ],
            cwd=BASE,
            label=f"STEP 2 [{i}/{n_total}]: {nb}",
            allow_failure=True,  # a broken notebook should not abort all others
        )
        if ok:
            n_ok += 1
    print(f"\nNotebooks: {n_ok}/{n_total} completed successfully.")


def step_latex():
    if not os.path.isdir(THESIS_DIR):
        print(f"WARNING: Thesis directory not found: {THESIS_DIR}. Skipping LaTeX.")
        return

    # Prefer latexmk (handles multiple passes + bibliography automatically)
    has_latexmk = subprocess.run(
        ["latexmk", "--version"], capture_output=True
    ).returncode == 0

    if has_latexmk:
        _run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=THESIS_DIR,
            label="STEP 3: latexmk (full compile)",
        )
    else:
        # Manual fallback: pdflatex → biber/bibtex → pdflatex × 2
        for i in range(1, 3):
            _run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=THESIS_DIR,
                label=f"STEP 3: pdflatex pass {i}",
            )
        # Try biber first, fall back to bibtex
        biber_ok = subprocess.run(
            ["biber", "main"], cwd=THESIS_DIR, capture_output=True
        ).returncode == 0
        if biber_ok:
            print("biber bibliography complete.")
        else:
            _run(["bibtex", "main"], cwd=THESIS_DIR, label="STEP 3: bibtex",
                 allow_failure=True)
        for i in range(3, 5):
            _run(
                ["pdflatex", "-interaction=nonstopmode", "main.tex"],
                cwd=THESIS_DIR,
                label=f"STEP 3: pdflatex pass {i}",
            )

    pdf = os.path.join(THESIS_DIR, "main.pdf")
    if os.path.exists(pdf):
        size_kb = os.path.getsize(pdf) // 1024
        print(f"\nPDF ready: {pdf}  ({size_kb} KB)")
    else:
        print("\nWARNING: main.pdf not found after compilation.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full reproducibility runner: pipeline → notebooks → LaTeX PDF"
    )
    parser.add_argument("--skip-notebooks", action="store_true",
                        help="Skip Jupyter notebook execution")
    parser.add_argument("--skip-latex", action="store_true",
                        help="Skip LaTeX PDF compilation")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _preflight_check()
    t_start = time.perf_counter()

    step_pipeline()

    if not args.skip_notebooks:
        step_notebooks()
    else:
        print("\nSkipping notebooks (--skip-notebooks).")

    if not args.skip_latex:
        step_latex()
    else:
        print("\nSkipping LaTeX (--skip-latex).")

    total = time.perf_counter() - t_start
    mins, secs = divmod(int(total), 60)
    print(f"\n{'=' * 60}")
    print(f"All steps complete in {mins}m {secs}s.")
    print(f"{'=' * 60}")
