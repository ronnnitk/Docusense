"""Add / refresh / remove documents across the vector index, question bank and registry."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import retrieval
from .mcq_parser import parse_mcqs
from .pdf_ingestion import chunk_pages, read_pdf
from .store import Store

INDEXED, UPDATED, UNCHANGED = "indexed", "updated", "unchanged"


@dataclass
class IngestResult:
    name: str
    status: str  # indexed (new) | updated (content changed) | unchanged (skipped, nothing recomputed)
    pages: int
    chunks: int
    mcqs: int
    with_answer: int


def _question_counts(store: Store, name: str) -> tuple[int, int]:
    qs = store.load_questions([name], generated=False)
    return len(qs), sum(1 for q in qs if q.answer)


def ingest_pdf(
    name: str, data: bytes, *, collection, embedder, store: Store, progress=None
) -> IngestResult:
    """Index one PDF. Re-uploading identical bytes does no embedding work at all.

    Raises PdfError for unusable files; on any failure the previous version of the
    document (if any) is left untouched.
    """
    sha = hashlib.sha256(data).hexdigest()
    existing = store.get_document(name)
    if existing and existing["sha256"] == sha and retrieval.has_document(collection, name):
        mcqs, with_answer = _question_counts(store, name)
        return IngestResult(name, UNCHANGED, existing["pages"], existing["chunks"], mcqs, with_answer)

    pages = read_pdf(name, data)
    chunks = chunk_pages(pages)
    retrieval.index_chunks(collection, embedder, name, chunks, progress)
    mcqs = parse_mcqs(pages)
    store.replace_questions(name, mcqs)  # also drops AI-generated questions made from the old text
    store.register_document(name, sha, len(pages), len(chunks))
    return IngestResult(
        name, UPDATED if existing else INDEXED, len(pages), len(chunks),
        len(mcqs), sum(1 for q in mcqs if q.answer),
    )


def remove_document(name: str, *, collection, store: Store) -> None:
    retrieval.delete_document(collection, name)
    store.delete_source(name)
    store.unregister_document(name)


def sync_registry(collection, store: Store) -> None:
    """Reconcile the SQLite registry with Chroma (one full scan; run once per server start).

    Covers databases created before the registry existed and an index folder that was
    deleted or restored by hand.
    """
    actual = {d["source"]: d for d in retrieval.list_documents(collection)}
    registered = {d["source"] for d in store.list_documents()}
    for source, d in actual.items():
        if source not in registered:
            store.register_document(source, None, d["pages"], d["chunks"])  # unknown hash: refreshed on next upload
    for source in registered - set(actual):
        store.unregister_document(source)
