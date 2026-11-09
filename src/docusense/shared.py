"""Streamlit-side shared resources used by every page (cached per server)."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import streamlit as st

from . import ingest, llm, retrieval
from .store import DEFAULT_DB, Store

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


USERS_DIR = Path(os.environ.get("DOCUSENSE_USERS_DIR", "data/users"))
USER_TTL_DAYS = 3
_UID_RE = re.compile(r"^[0-9a-f]{16}$")


def multiuser() -> bool:
    """Hosted (public) mode: every visitor gets private data. Local use stays single-user.

    On by default when a hosted LLM key is configured; override with DOCUSENSE_MULTIUSER=0/1.
    """
    flag = os.environ.get("DOCUSENSE_MULTIUSER")
    return flag == "1" if flag is not None else llm.use_groq()


def user_id() -> str | None:
    """A random private id per visitor, kept in the URL (?u=...) so a page refresh keeps the data.

    Anyone holding the link can open that workspace, so treat it like an unlisted link.
    """
    if not multiuser():
        return None
    ss = st.session_state
    if "uid" not in ss:
        uid = st.query_params.get("u", "")
        ss.uid = uid if _UID_RE.match(uid) else uuid.uuid4().hex[:16]
    if st.query_params.get("u") != ss.uid:
        st.query_params["u"] = ss.uid
    return ss.uid


@st.cache_resource
def _prune_old_users() -> int:
    """Delete workspaces untouched for USER_TTL_DAYS. Runs once per server start."""
    removed = 0
    cutoff = time.time() - USER_TTL_DAYS * 86400
    if USERS_DIR.is_dir():
        for d in USERS_DIR.iterdir():
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
    return removed


def _paths(uid: str | None) -> tuple[Path, Path]:
    if uid is None:
        return DEFAULT_DB, Path(os.environ.get("DOCUSENSE_CHROMA", "./chroma_db"))
    root = USERS_DIR / uid
    return root / "docusense.db", root / "chroma"


@st.cache_resource
def _collection_for(uid: str | None):
    return retrieval.open_collection(str(_paths(uid)[1]))


@st.cache_resource
def _store_for(uid: str | None) -> Store:
    store = Store(_paths(uid)[0])
    ingest.sync_registry(_collection_for(uid), store)  # once per workspace per server start
    return store


def get_collection():
    return _collection_for(user_id())


def get_store() -> Store:
    uid = user_id()
    if uid:
        _prune_old_users()
    s = _store_for(uid)
    if uid:
        os.utime(USERS_DIR / uid)  # mark the workspace active so it is not pruned
    return s


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
