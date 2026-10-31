import numpy as np
import pymupdf
import pytest

from docusense import ingest, retrieval
from docusense.pdf_ingestion import PdfError
from docusense.schemas import Chunk
from docusense.store import Store


class FakeEmbedder:
    """Deterministic 384-d vectors; counts how many texts it was asked to embed."""

    def __init__(self, fail_after: int | None = None):
        self.embedded = 0
        self.fail_after = fail_after

    def encode(self, texts, normalize_embeddings=True, **kw):
        if self.fail_after is not None and self.embedded >= self.fail_after:
            raise RuntimeError("embedder crashed")
        self.embedded += len(texts)
        rng = np.random.default_rng(len(texts))
        v = rng.normal(size=(len(texts), 384))
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def make_pdf(*page_texts):
    doc = pymupdf.open()
    for t in page_texts:
        doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 790), t, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def env(tmp_path):
    return dict(collection=retrieval.open_collection(str(tmp_path / "chroma")),
                store=Store(tmp_path / "t.db"), embedder=FakeEmbedder())


def test_documents_over_chromas_batch_limit_can_be_indexed(env):
    chunks = [Chunk(f"b_{i}", f"text {i}", "book.pdf", i // 4 + 1) for i in range(6000)]  # > 5461
    retrieval.index_chunks(env["collection"], env["embedder"], "book.pdf", chunks)
    assert env["collection"].count() == 6000


def test_reuploading_identical_file_does_no_embedding_work(env):
    data = make_pdf("alpha beta gamma " * 20, "delta epsilon " * 20)
    first = ingest.ingest_pdf("a.pdf", data, **env)
    embedded = env["embedder"].embedded
    again = ingest.ingest_pdf("a.pdf", data, **env)
    assert first.status == ingest.INDEXED and again.status == ingest.UNCHANGED
    assert env["embedder"].embedded == embedded                       # nothing recomputed
    assert (again.pages, again.chunks) == (first.pages, first.chunks)


def test_changed_file_is_replaced_not_duplicated(env):
    ingest.ingest_pdf("a.pdf", make_pdf("old content " * 20), **env)
    old = env["collection"].count()
    res = ingest.ingest_pdf("a.pdf", make_pdf("brand new content " * 20), **env)
    assert res.status == ingest.UPDATED and env["collection"].count() == old
    docs = env["store"].list_documents()
    assert [d["source"] for d in docs] == ["a.pdf"]


def test_unchanged_but_index_missing_is_reindexed(env):
    data = make_pdf("some text " * 20)
    ingest.ingest_pdf("a.pdf", data, **env)
    retrieval.delete_document(env["collection"], "a.pdf")             # index folder damaged
    assert ingest.ingest_pdf("a.pdf", data, **env).status != ingest.UNCHANGED
    assert retrieval.has_document(env["collection"], "a.pdf")


def test_failure_while_embedding_keeps_previous_version(env):
    ingest.ingest_pdf("a.pdf", make_pdf("version one " * 30), **env)
    before = env["collection"].get(where={"source": "a.pdf"})["documents"]
    broken = dict(env, embedder=FakeEmbedder(fail_after=0))
    with pytest.raises(RuntimeError):
        ingest.ingest_pdf("a.pdf", make_pdf("version two " * 30), **broken)
    assert env["collection"].get(where={"source": "a.pdf"})["documents"] == before


def test_unusable_pdf_raises_and_registers_nothing(env):
    with pytest.raises(PdfError):
        ingest.ingest_pdf("bad.pdf", b"not a pdf", **env)
    assert env["store"].list_documents() == []


def test_progress_callback_reports_up_to_total(env):
    calls = []
    ingest.ingest_pdf("a.pdf", make_pdf(*["word " * 150] * 30), progress=lambda d, t: calls.append((d, t)), **env)
    assert calls and calls[-1][0] == calls[-1][1]


def test_questions_are_stored_and_removed_with_document(env):
    quiz = make_pdf("Q1. x?\n(A) a\n(B) b\n(C) c\n(D) d\nAnswer: B\n")
    res = ingest.ingest_pdf("q.pdf", quiz, **env)
    assert (res.mcqs, res.with_answer) == (1, 1)
    assert ingest.ingest_pdf("q.pdf", quiz, **env).mcqs == 1          # counts survive an unchanged re-upload
    ingest.remove_document("q.pdf", collection=env["collection"], store=env["store"])
    assert env["store"].load_questions() == [] and env["store"].list_documents() == []
    assert not retrieval.has_document(env["collection"], "q.pdf")


def test_sync_registry_backfills_and_prunes(env):
    retrieval.index_chunks(env["collection"], env["embedder"], "old.pdf",
                           [Chunk("o_1", "hello", "old.pdf", 1), Chunk("o_2", "world", "old.pdf", 2)])
    env["store"].register_document("ghost.pdf", "abc", 3, 9)          # registry row with no vectors
    ingest.sync_registry(env["collection"], env["store"])
    docs = {d["source"]: d for d in env["store"].list_documents()}
    assert set(docs) == {"old.pdf"} and docs["old.pdf"]["chunks"] == 2 and docs["old.pdf"]["sha256"] is None
