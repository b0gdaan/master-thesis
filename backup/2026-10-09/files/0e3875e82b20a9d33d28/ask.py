"""Command-line Q&A over the thesis.

    python ask.py "Which model had the best RMSE?"   # one-shot
    python ask.py                                      # interactive loop
"""
from __future__ import annotations

import sys

import config
from rag import answer_question


def show(answer) -> None:
    print("\n" + answer.text + "\n")
    if answer.sources:
        print("- Sources -")
        seen = set()
        for s in answer.sources:
            label = s.label()
            if label not in seen:
                print(f"  - {label}")
                seen.add(label)


def main() -> None:
    config.use_utf8_stdout()

    import ingest

    if not config.CHROMA_DIR.exists():
        print("Building index (first run, downloads the embedding model)...")
        ingest.build_index(verbose=True)

    if len(sys.argv) > 1:
        show(answer_question(" ".join(sys.argv[1:])))
        return

    print("Thesis Copilot - ask a question (Ctrl-C to exit)")
    try:
        while True:
            question = input("\n> ").strip()
            if question:
                show(answer_question(question))
    except (KeyboardInterrupt, EOFError):
        print("\nbye")


if __name__ == "__main__":
    main()
