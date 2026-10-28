"""Streamlit-side shared resources used by every page (cached per server)."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from . import llm, retrieval
from .store import Store

ASSETS = Path(__file__).resolve().parents[2] / "assets"


@st.cache_resource
def get_embedder():
    return retrieval.load_embedder()


@st.cache_resource
def get_collection():
    return retrieval.open_collection()


@st.cache_resource
def get_store() -> Store:
    return Store()


@st.cache_data
def animation(name: str) -> dict:
    with open(ASSETS / name, "r", encoding="utf-8") as file:
        return json.load(file)


def init() -> None:
    """Per-run setup shared by all pages. Cheap: heavy models load lazily."""
    llm.set_cache(get_store())
    ss = st.session_state
    ss.setdefault("topics_text", "")
    ss.setdefault("coverage", None)


def indexed_sources() -> list[str]:
    return [d["source"] for d in retrieval.list_documents(get_collection())]


def topics() -> list[str]:
    return [t.strip() for t in st.session_state.topics_text.splitlines() if t.strip()]
