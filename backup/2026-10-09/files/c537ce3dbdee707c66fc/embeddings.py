"""Shared embedding model.

Local sentence-transformers embeddings (no API key, no cloud cost). The same
function is used at ingest time and at query time so the vectors always match.
"""
from __future__ import annotations

import config

_cache = None


def get_embeddings():
    """Return a cached HuggingFaceEmbeddings instance (loads the model once)."""
    global _cache
    if _cache is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _cache = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
    return _cache
