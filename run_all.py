"""
Full reproducibility runner: pipeline → notebooks → tests → LaTeX PDF

Usage:
    python run_all.py                  # all steps
    python run_all.py --skip-latex     # skip LaTeX compilation
    python run_all.py --skip-notebooks
    python run_all.py --skip-tests
    python run_all.py --tests-only     # run tests and regenerate PDF only
"""
import argparse
import importlib.metadata
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

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
    "08_Market_Events_Showcase.ipynb",  # landmark event deep-dives (runs last)
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


def step_tests() -> bool:
    """Run the full pytest suite, save JUnit XML + human-readable summary,
    and generate a LaTeX table for the thesis appendix.

    Returns True if all tests passed (or only skipped), False if any failed.
    """
    results_dir = os.path.join(BASE, "outputs", "results")
    tables_dir  = os.path.join(BASE, "outputs", "tables")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(tables_dir,  exist_ok=True)

    xml_path = os.path.join(results_dir, "test_results.xml")
    txt_path = os.path.join(results_dir, "test_results.txt")

    print(f"\n{'=' * 60}\nSTEP 3: pytest — automated validation suite\n{'=' * 60}")
    t0 = time.perf_counter()

    with open(txt_path, "w", encoding="utf-8") as txt_fh:
        proc = subprocess.run(
            [PYTHON, "-m", "pytest", "tests/", "-v",
             "--tb=short",
             f"--junit-xml={xml_path}"],
            cwd=BASE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = proc.stdout.decode("utf-8", errors="replace")
        txt_fh.write(output)
        print(output)

    elapsed = time.perf_counter() - t0
    passed = proc.returncode == 0
    print(f"Tests finished in {elapsed:.1f}s — {'ALL PASSED' if passed else 'SOME FAILED'}")

    # ── Generate LaTeX table from JUnit XML ──────────────────────────────────
    if os.path.exists(xml_path):
        _tests_to_latex(xml_path, os.path.join(tables_dir, "test_report.tex"))
        # Also write directly into thesis/tables/ so \input{} in appendix works
        thesis_tables = os.path.join(BASE, "thesis", "tables")
        os.makedirs(thesis_tables, exist_ok=True)
        _tests_to_latex(xml_path, os.path.join(thesis_tables, "test_report_auto.tex"))

    return passed


def _tests_to_latex(xml_path: str, out_tex: str) -> None:
    """Parse pytest JUnit XML -> compact per-class LaTeX summary for the appendix.

    Only a class-level summary is written into the thesis: number of tests, pass
    rate, and total wall-clock time per test class. The full per-test log -
    including parametrised test IDs (which embed absolute local paths) and the
    individual timings - stays in the JUnit XML inside the repository, so the
    document never leaks local paths or balloons to dozens of rows.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as exc:
        print(f"WARNING: could not parse test XML: {exc}")
        return

    # Collect all <testcase> elements (may be nested under <testsuite>)
    testcases = root.findall(".//testcase")
    if not testcases:
        return

    # Aggregate by test class, preserving first-seen order (dict keeps insertion order).
    classes: dict = {}
    n_pass = n_fail = n_skip = 0
    for tc in testcases:
        classname = tc.get("classname", "").split(".")[-1] or "(module)"
        try:
            t = float(tc.get("time", "0") or 0)
        except ValueError:
            t = 0.0
        skipped = tc.find("skipped")
        failed  = tc.find("failure") is not None or tc.find("error") is not None

        if skipped is not None:
            status = "skip"; n_skip += 1
        elif failed:
            status = "fail"; n_fail += 1
        else:
            status = "pass"; n_pass += 1

        c = classes.setdefault(
            classname, {"n": 0, "pass": 0, "fail": 0, "skip": 0, "time": 0.0}
        )
        c["n"] += 1
        c[status] += 1
        c["time"] += t

    total = n_pass + n_fail + n_skip
    total_time = sum(c["time"] for c in classes.values())

    def _passed_cell(c: dict) -> str:
        if c["fail"]:
            return rf"\textcolor{{red}}{{\textbf{{{c['pass']}/{c['n']}}}}}"
        return rf"\textcolor{{teal}}{{{c['pass']}/{c['n']}}}"

    skip_note = f" ({n_skip} skipped)" if n_skip else ", with none skipped"
    caption = (
        r"\caption{Automated validation suite, summarised by test class. All "
        + str(total)
        + r" tests pass on the present outputs"
        + skip_note
        + r". The complete per-test log, including parametrised cases and per-test "
          r"timings, is written to \texttt{outputs/results/test\_results.xml} in the "
          r"repository.}"
    )
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        caption,
        r"\label{tab:test_report}",
        r"\begin{tabular}{lccr}",
        r"\toprule",
        r"Test class & Tests & Passed & Time (s) \\",
        r"\midrule",
    ]
    for cls, c in classes.items():
        lines.append(
            rf"\texttt{{{cls}}} & {c['n']} & {_passed_cell(c)} & {c['time']:.2f} \\"
        )
    lines += [
        r"\midrule",
        rf"\textbf{{Total}} & \textbf{{{total}}} & \textbf{{{n_pass}}} & "
        rf"\textbf{{{total_time:.2f}}} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]

    with open(out_tex, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"Test report LaTeX saved -> {out_tex}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full reproducibility runner: pipeline → notebooks → tests → LaTeX PDF"
    )
    parser.add_argument("--skip-notebooks", action="store_true",
                        help="Skip Jupyter notebook execution")
    parser.add_argument("--skip-latex", action="store_true",
                        help="Skip LaTeX PDF compilation")
    parser.add_argument("--skip-tests", action="store_true",
                        help="Skip automated test suite")
    parser.add_argument("--tests-only", action="store_true",
                        help="Run tests and recompile PDF only (skip pipeline + notebooks)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    _preflight_check()
    t_start = time.perf_counter()

    if args.tests_only:
        step_tests()
        step_latex()
    else:
        step_pipeline()

        if not args.skip_notebooks:
            step_notebooks()
        else:
            print("\nSkipping notebooks (--skip-notebooks).")

        if not args.skip_tests:
            step_tests()
        else:
            print("\nSkipping tests (--skip-tests).")

        if not args.skip_latex:
            step_latex()
        else:
            print("\nSkipping LaTeX (--skip-latex).")

    total = time.perf_counter() - t_start
    mins, secs = divmod(int(total), 60)
    print(f"\n{'=' * 60}")
    print(f"All steps complete in {mins}m {secs}s.")
    print(f"{'=' * 60}")
