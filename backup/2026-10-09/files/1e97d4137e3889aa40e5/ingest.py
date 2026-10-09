"""Build the vector index from the documents in ``data/``.

Loads every PDF (page by page, keeping the page number for citations) and every
Markdown/text file, splits them into overlapping chunks, embeds them locally and
persists everything to a Chroma database.

    python ingest.py            # build (or add to) the index
    python ingest.py --reset    # delete the existing index and rebuild

`ensure_index()` is used by the app and CLI to self-build the index on a fresh
deploy (e.g. Hugging Face Spaces), where the database is not committed.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from embeddings import get_embeddings


def load_pdf(path: Path) -> list[Document]:
    """One Document per non-empty page, tagged with its 1-based page number."""
    docs: list[Document] = []
    with fitz.open(path) as pdf:
        for i, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if not text:
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": path.name, "page": i + 1, "type": "pdf"},
                )
            )
    return docs


def load_text(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [Document(page_content=text, metadata={"source": path.name, "type": "text"})]


def load_documents(data_dir: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(data_dir.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            docs += load_pdf(path)
        elif suffix in {".md", ".txt"}:
            docs += load_text(path)
    return docs


def build_index(reset: bool = False, verbose: bool = False) -> int:
    """Load, chunk, embed and persist the documents. Returns the chunk count."""
    from langchain_chroma import Chroma

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    if reset and config.CHROMA_DIR.exists():
        shutil.rmtree(config.CHROMA_DIR)
        log(f"Removed existing index at {config.CHROMA_DIR}")

    docs = load_documents(config.DATA_DIR)
    log(f"Loaded {len(docs)} source document(s) from {config.DATA_DIR}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        add_start_index=True,
    )
    chunks = splitter.split_documents(docs)
    log(f"Split into {len(chunks)} chunks")

    log(f"Embedding with {config.EMBEDDING_MODEL} (first run downloads the model)…")
    Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
    )
    return len(chunks)


def ensure_index() -> None:
    """Build the index if it does not exist yet (used on fresh deploys)."""
    if not config.CHROMA_DIR.exists():
        build_index()


def main() -> None:
    config.use_utf8_stdout()
    parser = argparse.ArgumentParser(description="Build the Thesis Copilot index.")
    parser.add_argument(
        "--reset", action="store_true", help="Delete the existing index first."
    )
    args = parser.parse_args()

    n = build_index(reset=args.reset, verbose=True)
    print(f"✓ Indexed {n} chunks into {config.CHROMA_DIR}")


if __name__ == "__main__":
    main()
