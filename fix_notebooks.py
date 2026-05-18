"""
Fix all notebooks:
- NB 01-06: remove duplicate ROOT detection block, fix build_paths to use ROOT
- NB 07: replace fragile BASE = os.path.abspath(...) with proper ROOT detection
"""
import json
import os

NB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notebooks")

# ─────────────────────────────────────────────────────────
# Notebooks 01-06: fix path and remove duplicate ROOT block
# ─────────────────────────────────────────────────────────
OLD_SETUP = (
    "from pathlib import Path\n"
    "import sys\n"
    "ROOT = next(\n"
    "    str(p) for p in [Path.cwd(), Path.cwd().parent, Path.cwd().parent.parent]\n"
    "    if (p / 'config.yaml').exists()\n"
    ")\n"
    "if ROOT not in sys.path:\n"
    "    sys.path.insert(0, ROOT)\n"
    "\n"
    "import sys, os\n"
    "# Add project root to path"
)

NEW_SETUP = "import sys, os"

NBS_06 = [
    "01_EDA_Dataset.ipynb",
    "02_GridSearch.ipynb",
    "03_Model_Comparison.ipynb",
    "04_DM_Tests_Visuals.ipynb",
    "05_XGB_vs_DCC.ipynb",
    "06_Regime_Analysis.ipynb",
]

for nb_name in NBS_06:
    nb_path = os.path.join(NB_DIR, nb_name)
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    changed = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])

        # Fix duplicate ROOT block
        if OLD_SETUP in src:
            src = src.replace(OLD_SETUP, NEW_SETUP)
            changed += 1

        # Fix build_paths call (both quote styles)
        new_src = src.replace("build_paths(cfg['base_dir'])", "build_paths(ROOT)")
        new_src = new_src.replace('build_paths(cfg["base_dir"])', "build_paths(ROOT)")
        if new_src != src:
            src = new_src
            changed += 1

        cell["source"] = [src]

    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f"{nb_name}: {changed} replacements")

# ─────────────────────────────────────────────────────────
# Notebook 07: replace manual BASE path with ROOT detection
# ─────────────────────────────────────────────────────────
NB07_PATH = os.path.join(NB_DIR, "07_Robustness_Checks.ipynb")

OLD_BASE = (
    "BASE      = os.path.abspath(os.path.join(os.getcwd(), '..'))\n"
    "RESULTS   = os.path.join(BASE, 'outputs', 'results')\n"
    "FIGURES   = os.path.join(BASE, 'outputs', 'figures')"
)

NEW_BASE = (
    "from pathlib import Path as _Path\n"
    "ROOT = next(\n"
    "    str(p) for p in [_Path.cwd(), _Path.cwd().parent, _Path.cwd().parent.parent]\n"
    "    if (p / 'config.yaml').exists()\n"
    ")\n"
    "if ROOT not in sys.path:\n"
    "    import sys as _sys\n"
    "    _sys.path.insert(0, ROOT)\n"
    "RESULTS   = os.path.join(ROOT, 'outputs', 'results')\n"
    "FIGURES   = os.path.join(ROOT, 'outputs', 'figures')"
)

with open(NB07_PATH, "r", encoding="utf-8") as f:
    nb7 = json.load(f)

changed7 = 0
for cell in nb7["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])

    if "BASE      = os.path.abspath(os.path.join(os.getcwd(), '..'))" in src:
        src = src.replace(OLD_BASE, NEW_BASE)
        # Also remove the old print lines that use BASE
        src = src.replace("print('Base dir:', BASE)\n", "print('Base dir:', ROOT)\n")
        src = src.replace("print('Results :', RESULTS)", "print('Results :', RESULTS)")
        changed7 += 1

    cell["source"] = [src]

with open(NB07_PATH, "w", encoding="utf-8") as f:
    json.dump(nb7, f, ensure_ascii=False, indent=1)

print(f"07_Robustness_Checks.ipynb: {changed7} replacements")
print("\nAll notebooks patched successfully.")
