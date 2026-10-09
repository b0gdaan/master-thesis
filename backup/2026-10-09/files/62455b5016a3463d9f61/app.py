"""Streamlit chat UI for Thesis Copilot.

    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import config
from rag import answer_question

st.set_page_config(page_title="Thesis Copilot", page_icon="\U0001F4C8", layout="centered")


@st.cache_resource(show_spinner="Building the thesis index (first run, ~1-2 min)...")
def _ensure_index_ready() -> bool:
    """On a fresh deploy the Chroma index isn't committed — build it once here."""
    import ingest

    ingest.ensure_index()
    return True


_ensure_index_ready()

st.title("\U0001F4C8 Thesis Copilot")
st.caption(
    "RAG Q&A over the master's thesis *Forecasting Time-Varying Intermarket "
    "Dependencies Between Cryptocurrencies and Conventional Assets Using Machine "
    "Learning*. Answers are grounded in the thesis text, with page citations."
)


def render_sources(sources) -> None:
    if not sources:
        return
    with st.expander("Sources"):
        for s in sources:
            st.caption(s.label())
            st.text(s.snippet + "...")


with st.sidebar:
    st.header("About")
    llm_line = (
        f"`{config.resolved_model()}` via {config.LLM_PROVIDER}"
        if config.llm_is_configured()
        else "_not configured - retrieval-only mode_"
    )
    st.markdown(
        "- **Retriever:** sentence-transformers (local, multilingual)\n"
        "- **Vector store:** Chroma\n"
        f"- **LLM:** {llm_line}"
    )
    st.markdown("Ask in English, Serbian, or Russian.")
    st.divider()
    st.markdown("**Try one:**")
    examples = [
        "Which model had the best RMSE, and why?",
        "Why does DCC-GARCH perform worst?",
        "What is the investor signal layer for?",
        "Почему простые модели обошли сложные?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["pending"] = ex

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        render_sources(m.get("sources"))

prompt = st.chat_input("Ask about the thesis...") or st.session_state.pop("pending", None)

if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Searching the thesis..."):
            answer = answer_question(prompt)
        st.markdown(answer.text)
        render_sources(answer.sources)
    st.session_state["messages"].append(
        {"role": "assistant", "content": answer.text, "sources": answer.sources}
    )
