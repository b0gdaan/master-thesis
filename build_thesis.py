#!/usr/bin/env python3
"""Build the master thesis PDF with a single command.

Usage
-----
    python build_thesis.py            full build (latexmk, or pdflatex+biber fallback)
    python build_thesis.py --check    verify toolchain and file dependencies, do not build
    python build_thesis.py --quick    one pdflatex pass; fast preview while proofreading
    python build_thesis.py --clean    delete auxiliary files, then build
    python build_thesis.py --open     open the PDF when the build finishes

Only the Python standard library is used, so this runs on a fresh machine
without creating a virtual environment. LaTeX itself (MiKTeX on Windows,
TeX Live on macOS/Linux) still has to be installed; --check reports what is
missing and where to get it.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
THESIS_DIR = os.path.join(BASE, "thesis")
MAIN = "main.tex"
PDF = os.path.join(THESIS_DIR, "main.pdf")

AUX_SUFFIXES = (
    ".aux", ".bbl", ".bcf", ".blg", ".fdb_latexmk", ".fls", ".lof", ".log",
    ".lot", ".out", ".run.xml", ".toc", ".synctex.gz",
)

INSTALL_HINT = {
    "win32": "MiKTeX: https://miktex.org/download  (choose the Basic MiKTeX Installer)",
    "darwin": "MacTeX: https://tug.org/mactex/  (or `brew install --cask mactex-no-gui`)",
}.get(sys.platform, "TeX Live: `sudo apt install texlive-full biber latexmk`")


def _c(text: str, colour: str) -> str:
    """Colourise for terminals that support ANSI; plain text elsewhere."""
    if not sys.stdout.isatty():
        return text
    codes = {"red": "31", "green": "32", "yellow": "33", "blue": "36", "bold": "1"}
    return f"\033[{codes[colour]}m{text}\033[0m"


def banner(text: str) -> None:
    print(f"\n{'=' * 62}\n{text}\n{'=' * 62}")


# ──────────────────────────────────────────────────────────────────────────
# Dependency verification
# ──────────────────────────────────────────────────────────────────────────
def collect_dependencies() -> set[str]:
    """Return every path referenced by \\input or \\includegraphics."""
    deps: set[str] = set()
    sources = [os.path.join(THESIS_DIR, MAIN)]
    chapters = os.path.join(THESIS_DIR, "chapters")
    if os.path.isdir(chapters):
        sources += [
            os.path.join(chapters, f) for f in sorted(os.listdir(chapters))
            if f.endswith(".tex")
        ]
    pattern = re.compile(r"\\(?:input|includegraphics)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
    for src in sources:
        with open(src, encoding="utf-8", errors="replace") as fh:
            for match in pattern.finditer(fh.read()):
                deps.add(match.group(1).strip())
    return deps


def check_dependencies(verbose: bool = True) -> list[str]:
    """Report referenced files that are absent. Returns the missing ones."""
    missing = []
    for dep in sorted(collect_dependencies()):
        # Resolved by the TeX distribution itself, not a project file.
        if dep in {"glyphtounicode"}:
            continue
        base = os.path.normpath(os.path.join(THESIS_DIR, dep))
        if not any(os.path.isfile(base + ext) for ext in ("", ".tex", ".png", ".pdf", ".jpg")):
            missing.append(dep)
    if verbose:
        total = len(collect_dependencies())
        if missing:
            print(_c(f"  {len(missing)} of {total} referenced files are MISSING:", "red"))
            for m in missing:
                print(f"    - {m}")
        else:
            print(_c(f"  all {total} referenced files present", "green"))
    return missing


def check_toolchain(verbose: bool = True) -> dict[str, str | None]:
    tools = {name: shutil.which(name) for name in ("latexmk", "pdflatex", "biber", "bibtex")}
    if verbose:
        for name, path in tools.items():
            mark = _c("OK     ", "green") if path else _c("missing", "yellow")
            print(f"  {mark} {name:9s} {path or ''}")
    return tools


# ──────────────────────────────────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────────────────────────────────
def run(cmd: list[str], label: str) -> int:
    print(_c(f"\n> {label}", "blue"))
    print(f"  {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=THESIS_DIR, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    output = proc.stdout.decode("utf-8", errors="replace")
    # Surface only real problems; the full transcript lives in main.log.
    for line in output.splitlines():
        if re.match(r"^(!|.*Emergency stop|.*Fatal error)", line):
            print(_c(f"  {line}", "red"))
    return proc.returncode


def clean_aux() -> None:
    removed = 0
    for entry in os.listdir(THESIS_DIR):
        if entry.startswith("main") and entry.endswith(AUX_SUFFIXES):
            os.remove(os.path.join(THESIS_DIR, entry))
            removed += 1
    print(f"  removed {removed} auxiliary files")


def summarise_log() -> bool:
    """Print page count, undefined references and overfull boxes. True if clean."""
    log_path = os.path.join(THESIS_DIR, "main.log")
    if not os.path.isfile(log_path):
        print(_c("  main.log not found — build did not run", "red"))
        return False
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        log = fh.read()

    pages = re.findall(r"Output written on main\.pdf \((\d+) pages?", log)
    undefined_refs = len(re.findall(r"Reference `[^']*' on page \d+ undefined", log))
    undefined_cites = len(re.findall(r"Citation `[^']*' on page \d+ undefined", log))
    overfull = re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)", log)
    big_overfull = [float(x) for x in overfull if float(x) >= 10]

    print()
    print(f"  pages                : {pages[-1] if pages else _c('NOT PRODUCED', 'red')}")
    for label, count in (("undefined references", undefined_refs),
                         ("undefined citations", undefined_cites)):
        print(f"  {label:21s}: {_c(str(count), 'red' if count else 'green')}")
    worst = f"{max(big_overfull):.0f}pt" if big_overfull else "-"
    print(f"  overfull boxes >=10pt: {_c(str(len(big_overfull)), 'yellow' if big_overfull else 'green')}"
          f"{'  (worst ' + worst + ')' if big_overfull else ''}")
    return bool(pages) and not undefined_refs and not undefined_cites


def build(quick: bool, tools: dict[str, str | None]) -> int:
    if quick:
        if not tools["pdflatex"]:
            return 1
        return run([tools["pdflatex"], "-interaction=nonstopmode", MAIN],
                   "pdflatex (single quick pass)")

    if tools["latexmk"]:
        # latexmk resolves the pdflatex/biber/pdflatex ordering by itself.
        return run([tools["latexmk"], "-pdf", "-interaction=nonstopmode",
                    "-halt-on-error", MAIN], "latexmk (full build)")

    if not tools["pdflatex"]:
        return 1
    print(_c("\n  latexmk not found — using the manual pdflatex/biber sequence", "yellow"))
    run([tools["pdflatex"], "-interaction=nonstopmode", MAIN], "pdflatex pass 1")
    if tools["biber"]:
        run([tools["biber"], "main"], "biber (bibliography)")
    elif tools["bibtex"]:
        run([tools["bibtex"], "main"], "bibtex (bibliography)")
    else:
        print(_c("  no biber/bibtex — citations will render as [?]", "yellow"))
    run([tools["pdflatex"], "-interaction=nonstopmode", MAIN], "pdflatex pass 2")
    return run([tools["pdflatex"], "-interaction=nonstopmode", MAIN], "pdflatex pass 3")


def open_pdf() -> None:
    if not os.path.isfile(PDF):
        return
    if sys.platform == "win32":
        os.startfile(PDF)  # noqa: S606
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", PDF])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the master thesis PDF.")
    parser.add_argument("--check", action="store_true",
                        help="verify toolchain and files, then exit")
    parser.add_argument("--quick", action="store_true",
                        help="single pdflatex pass (fast preview, references may lag)")
    parser.add_argument("--clean", action="store_true",
                        help="delete auxiliary files before building")
    parser.add_argument("--open", action="store_true",
                        help="open the PDF when finished")
    args = parser.parse_args()

    if not os.path.isfile(os.path.join(THESIS_DIR, MAIN)):
        print(_c(f"thesis/{MAIN} not found next to this script.", "red"))
        print(f"Script location: {BASE}")
        print("Run it from inside the repository, e.g. `python build_thesis.py`.")
        return 1

    banner("Environment check")
    tools = check_toolchain()
    missing_files = check_dependencies()

    if not tools["pdflatex"]:
        print(_c("\nLaTeX is not installed (pdflatex not on PATH).", "red"))
        print(f"Install it first:\n  {INSTALL_HINT}")
        print("\nOn Windows, reopen the terminal after installing so PATH is refreshed.")
        return 1
    if missing_files:
        print(_c("\nCannot build: referenced files are missing (see the list above).", "red"))
        print("If this is a fresh clone, the figures live in outputs/figures/ and are")
        print("tracked in git; run `git status` to check nothing was left behind.")
        return 1
    if args.check:
        print(_c("\nEnvironment is ready to build.", "green"))
        return 0

    if args.clean:
        banner("Cleaning auxiliary files")
        clean_aux()

    banner("Building" + (" (quick pass)" if args.quick else ""))
    started = time.time()
    code = build(args.quick, tools)

    banner("Result")
    clean = summarise_log()
    print(f"  build time           : {time.time() - started:.1f}s")
    if os.path.isfile(PDF):
        print(f"  PDF                  : {PDF}  ({os.path.getsize(PDF) // 1024} KB)")

    if args.quick:
        print(_c("\n  Quick pass done. Cross-references and the bibliography may be stale;", "yellow"))
        print(_c("  run without --quick before printing.", "yellow"))
    elif clean and code == 0:
        print(_c("\n  Build finished cleanly.", "green"))
    else:
        print(_c("\n  Build finished with problems — see thesis/main.log.", "yellow"))

    if args.open:
        open_pdf()
    return 0 if os.path.isfile(PDF) else 1


if __name__ == "__main__":
    sys.exit(main())
