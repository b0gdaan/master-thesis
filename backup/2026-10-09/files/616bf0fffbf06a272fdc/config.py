"""Central configuration for Thesis Copilot (RAG over the master's thesis).

All tunables live here so the ingest script, the core RAG logic, the CLI and the
Streamlit UI share one source of truth. Values can be overridden via a `.env`
file (see `.env.example`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Paths -------------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "thesis"

# --- Chunking ----------------------------------------------------------------
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# --- Embeddings --------------------------------------------------------------
# Local, free, multilingual: the thesis body is English, the abstract/title are
# Serbian (Cyrillic), and questions may come in Russian or Serbian. A
# multilingual model keeps cross-lingual retrieval working.
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# --- Retrieval ---------------------------------------------------------------
TOP_K = int(os.getenv("TOP_K", "5"))

# --- LLM (answer generation) -------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")  # blank -> per-provider default below
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
}


def llm_is_configured() -> bool:
    """True when an API key is present for the selected provider."""
    if LLM_PROVIDER == "groq":
        return bool(GROQ_API_KEY)
    if LLM_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    return False


def resolved_model() -> str:
    return LLM_MODEL or DEFAULT_MODELS.get(LLM_PROVIDER, "")


def use_utf8_stdout() -> None:
    """Windows consoles default to cp1252 and crash when printing Cyrillic.

    Force UTF-8 so the CLI can echo Serbian/Russian text safely.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
