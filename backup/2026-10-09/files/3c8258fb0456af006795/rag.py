"""Core Retrieval-Augmented Generation logic.

`answer_question` retrieves the most relevant thesis passages and, when an LLM
key is configured, asks the model for a grounded answer. With no key it returns
the retrieved passages directly (semantic search works fully offline). Both the
CLI (`ask.py`) and the Streamlit app (`app.py`) call into here.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

import config
from embeddings import get_embeddings

SYSTEM_PROMPT = (
    "You are Thesis Copilot, an assistant that answers questions about a master's "
    "thesis titled 'Forecasting Time-Varying Intermarket Dependencies Between "
    "Cryptocurrencies and Conventional Assets Using Machine Learning'.\n"
    "Answer ONLY from the context below. If the answer is not in the context, say "
    "you don't find it in the thesis. Be concise and precise, and quote concrete "
    "numbers (RMSE, R-squared, etc.) when they appear. Reply in the same language "
    "as the question."
)

PROMPT_TEMPLATE = (
    "{system}\n\n"
    "=== CONTEXT ===\n{context}\n\n"
    "=== QUESTION ===\n{question}\n\n"
    "=== ANSWER ==="
)


@dataclass
class Source:
    source: str
    page: int | None
    snippet: str

    def label(self) -> str:
        return self.source + (f", p.{self.page}" if self.page else "")


@dataclass
class Answer:
    text: str
    sources: list[Source]
    generated: bool  # True if an LLM wrote the answer, False if retrieval-only


def get_vectorstore():
    from langchain_chroma import Chroma

    if not config.CHROMA_DIR.exists():
        raise FileNotFoundError(
            f"No index found at {config.CHROMA_DIR}. Run `python ingest.py` first."
        )
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        persist_directory=str(config.CHROMA_DIR),
        embedding_function=get_embeddings(),
    )


def _format_context(docs: list[Document]) -> str:
    blocks = []
    for d in docs:
        tag = d.metadata.get("source", "?")
        if d.metadata.get("page"):
            tag += f", p.{d.metadata['page']}"
        blocks.append(f"[{tag}]\n{d.page_content}")
    return "\n\n".join(blocks)


def _to_sources(docs: list[Document]) -> list[Source]:
    return [
        Source(
            source=d.metadata.get("source", "?"),
            page=d.metadata.get("page"),
            snippet=d.page_content[:300].strip(),
        )
        for d in docs
    ]


def _get_llm():
    provider = config.LLM_PROVIDER
    model = config.resolved_model()
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model, temperature=config.LLM_TEMPERATURE, api_key=config.GROQ_API_KEY
        )
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (use 'groq' or 'openai').")


def answer_question(question: str, k: int | None = None) -> Answer:
    k = k or config.TOP_K
    vectorstore = get_vectorstore()
    docs = vectorstore.similarity_search(question, k=k)
    sources = _to_sources(docs)

    if not config.llm_is_configured():
        msg = (
            "No LLM API key is configured, so I can't write a generated answer. "
            "Below are the most relevant passages from the thesis (semantic search "
            "runs fully offline). Set GROQ_API_KEY in .env to enable written answers."
        )
        return Answer(text=msg, sources=sources, generated=False)

    llm = _get_llm()
    prompt = PROMPT_TEMPLATE.format(
        system=SYSTEM_PROMPT,
        context=_format_context(docs),
        question=question,
    )
    response = llm.invoke(prompt)
    text = getattr(response, "content", str(response))
    return Answer(text=text, sources=sources, generated=True)
