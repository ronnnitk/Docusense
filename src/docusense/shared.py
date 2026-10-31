"""Streamlit-side shared resources used by every page (cached per server)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import streamlit as st

from . import ingest, llm, retrieval
from .store import Store

ASSETS = Path(__file__).resolve().parents[2] / "assets"

# The embedding model takes tens of seconds to import and load, and Ollama needs ~10 s to
# load its model on the first request. Both are started in the background when the server
# starts, so by the time you upload or ask something they are usually ready.
_embedder = None
_embedder_lock = threading.Lock()
_warm_lock = threading.Lock()
_warm_started = False


def get_embedder():
    """Load once per server process; safe to call from the warm-up thread and from pages."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = retrieval.load_embedder()
        return _embedder


def start_warmup() -> None:
    global _warm_started
    if os.environ.get("DOCUSENSE_NO_WARMUP"):
        return
    with _warm_lock:
        if _warm_started:
            return
        _warm_started = True

    def safe(fn):
        try:
            fn()
        except Exception:
            pass  # a failed warm-up just means the first real request pays the cost

    for fn in (get_embedder, llm.warm_up):
        threading.Thread(target=safe, args=(fn,), name=f"docusense-warm-{fn.__name__}", daemon=True).start()


@st.cache_resource
def get_collection():
    return retrieval.open_collection()


@st.cache_resource
def get_store() -> Store:
    store = Store()
    ingest.sync_registry(get_collection(), store)  # once per server start
    return store


@st.cache_data
def animation(name: str) -> dict:
    with open(ASSETS / name, "r", encoding="utf-8") as file:
        return json.load(file)


def init() -> None:
    """Per-run setup shared by all pages. Cheap: heavy models load in the background."""
    llm.set_cache(get_store())
    start_warmup()
    ss = st.session_state
    ss.setdefault("topics_text", "")
    ss.setdefault("coverage", None)


def indexed_sources() -> list[str]:
    """From the SQLite registry: O(documents), not a scan of every chunk."""
    return [d["source"] for d in get_store().list_documents()]


def topics() -> list[str]:
    return [t.strip() for t in st.session_state.topics_text.splitlines() if t.strip()]


def embedder():
    """The embedding model, with a visible message if it is still loading in the background."""
    if _embedder is None:
        with st.spinner("Loading the embedding model (first run only, can take up to a minute)..."):
            return get_embedder()
    return _embedder
