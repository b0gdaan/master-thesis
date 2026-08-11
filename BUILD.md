# Building the thesis on another machine

Everything the PDF needs is in git, so a clone compiles without running the
Python pipeline. Only a LaTeX distribution is required.

## Setup (once)

1. **Install LaTeX**
   - Windows: [MiKTeX](https://miktex.org/download) — Basic installer.
     Reopen the terminal afterwards so `PATH` picks it up.
   - macOS: `brew install --cask mactex-no-gui`
   - Linux: `sudo apt install texlive-full biber latexmk`

2. **Clone the repository**

   ```bash
   git clone --depth 1 https://github.com/b0gdaan/master-thesis.git
   cd master-thesis
   ```

   `--depth 1` skips the history and downloads ~36 MB instead of ~130 MB.
   Drop the flag if the full history is wanted.

3. **Check the environment**

   ```bash
   python build_thesis.py --check
   ```

   This verifies the toolchain and that all 48 files referenced by
   `\input`/`\includegraphics` are present, without starting a build.

## Building

```bash
python build_thesis.py           # full build: pdflatex + biber + pdflatex x2
python build_thesis.py --quick   # single pass, for a fast look while editing
python build_thesis.py --clean   # discard aux files first, then build
python build_thesis.py --open    # open the PDF when finished
```

A clean full build takes roughly 45 s and reports the page count, undefined
references and overfull boxes. The current expected result is
**75 pages, 0 undefined references, 0 overfull boxes**; anything else means a
change introduced a problem. On the first run MiKTeX may pause to install
missing packages — allow it.

`--quick` skips the bibliography and the second pass, so cross-references and
citations can lag by one build. Always finish with a full build before
printing.

## What lives where

| Path | Contents |
|---|---|
| `thesis/main.tex` | Title data, committee, abstracts, document order |
| `thesis/chapters/` | Chapters 1–6 and Appendices A–F |
| `thesis/references.bib` | Bibliography |
| `thesis/finthesis.cls` | University template (title pages, layout) |
| `outputs/figures/` | Every figure the thesis includes |

Regenerating figures and result tables requires the full Python pipeline
(`python run_all.py`), which needs the dependencies in `requirements.txt`
and takes about two hours. That is unnecessary for proofreading or printing:
the figures and the PDF in the repository are already the current ones.

## The fourth title page (print vs. repository)

The template puts a scan of the approved thesis application on the fourth title
page. That document carries the names of the commission members and the
official file numbers, so it is **not** kept in the repository: `.gitignore`
excludes `thesis/finthesis_assets/thesis_application.pdf`.

`main.tex` decides at build time with `\IfFileExists`:

| Asset present | Result |
|---|---|
| no (a fresh clone) | **75 pages**, no fourth title page, builds fine |
| yes (local print build) | **76 pages**, application page included |

So a build on this machine overwrites `thesis/main.pdf` with the 76-page
version. The repository is meant to keep the 75-page one, so before committing:

```bash
git checkout -- thesis/main.pdf
```

The print-ready copy lives beside it as `thesis/main_print.pdf`, which is
git-ignored.

## Before printing

- `\date{...}` in `thesis/main.tex` sets the date on the assignment page
  (currently 19 May 2026, the date the topic was assigned). Change it only if
  the faculty asks for the defense date there.
- Copies needed: one per commission member (5) plus one for the university
  archive, plus one copy on disk.
- The title page must carry the university logo introduced in March 2026 — the
  circular one in `thesis/finthesis_assets/unikg_logo.png`, not the old coat of
  arms that ships with the template.
