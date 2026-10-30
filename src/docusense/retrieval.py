"""Embeddings + Chroma storage. Incremental per-document indexing."""
from __future__ import annotations

import os
from collections import defaultdict

import chromadb

from .schemas import Chunk, Hit

COLLECTION = "docusense_documents"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


def open_collection(path: str | None = None):
    path = path or os.environ.get("DOCUSENSE_CHROMA", "./chroma_db")
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def index_chunks(collection, embedder, source: str, chunks: list[Chunk]) -> None:
    """Replace ONLY this file's chunks; other documents stay untouched."""
    collection.delete(where={"source": source})
    if not chunks:
        return
    vectors = embedder.encode([c.text for c in chunks], normalize_embeddings=True).tolist()
    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=vectors,
        metadatas=[{"source": c.source, "page": c.page} for c in chunks],
    )


def delete_document(collection, source: str) -> None:
    collection.delete(where={"source": source})


def list_documents(collection) -> list[dict]:
    if collection.count() == 0:
        return []
    metas = collection.get(include=["metadatas"])["metadatas"]
    chunks, pages = defaultdict(int), defaultdict(set)
    for m in metas:
        chunks[m["source"]] += 1
        pages[m["source"]].add(m["page"])
    return [
        {"source": s, "chunks": chunks[s], "pages": len(pages[s])}
        for s in sorted(chunks)
    ]


def search(
    collection, embedder, query: str, k: int = 4, sources: list[str] | None = None
) -> list[Hit]:
    if collection.count() == 0:
        return []
    vector = embedder.encode([query], normalize_embeddings=True).tolist()
    where = None
    if sources:
        where = {"source": sources[0]} if len(sources) == 1 else {"source": {"$in": sources}}
    res = collection.query(
        query_embeddings=vector,
        n_results=min(k, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return [
        Hit(text=doc, source=meta["source"], page=meta["page"], distance=dist)
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]


def diverse_search(
    collection, embedder, query: str, k: int = 8, per_file: int = 3
) -> list[Hit]:
    """Top hits but capped per file, so one big document can't crowd out the rest."""
    pool = search(collection, embedder, query, k=k * 3)
    taken, count = [], defaultdict(int)
    for h in pool:
        if count[h.source] < per_file:
            taken.append(h)
            count[h.source] += 1
        if len(taken) == k:
            break
    return taken
