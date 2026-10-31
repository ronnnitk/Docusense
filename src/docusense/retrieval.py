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


EMBED_BATCH = 64
ADD_BATCH = 2000  # Chroma rejects single calls above ~5461 records


def embed_chunks(embedder, chunks: list[Chunk], progress=None) -> list[list[float]]:
    """Embed in batches so callers can show progress (done, total)."""
    vectors: list[list[float]] = []
    for i in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[i:i + EMBED_BATCH]
        vectors.extend(
            embedder.encode(
                [c.text for c in batch], normalize_embeddings=True,
                batch_size=EMBED_BATCH, show_progress_bar=False,
            ).tolist()
        )
        if progress:
            progress(len(vectors), len(chunks))
    return vectors


def index_chunks(collection, embedder, source: str, chunks: list[Chunk], progress=None) -> None:
    """Replace ONLY this file's chunks; other documents stay untouched.

    The slow part (embedding) happens BEFORE anything is deleted, so an error or an
    interrupted run leaves the previous version of the document intact.
    """
    vectors = embed_chunks(embedder, chunks, progress) if chunks else []
    collection.delete(where={"source": source})
    try:
        for i in range(0, len(chunks), ADD_BATCH):
            part = chunks[i:i + ADD_BATCH]
            collection.add(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                embeddings=vectors[i:i + ADD_BATCH],
                metadatas=[{"source": c.source, "page": c.page} for c in part],
            )
    except Exception:
        collection.delete(where={"source": source})  # never leave a half-indexed document
        raise


def has_document(collection, source: str) -> bool:
    return bool(collection.get(where={"source": source}, limit=1, include=[])["ids"])


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
