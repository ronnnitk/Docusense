import pymupdf
import pytest

from docusense.mcq_parser import parse_mcqs
from docusense.pdf_ingestion import PdfError, chunk_pages, chunk_text, read_pdf


def make_pdf(pages):
    doc = pymupdf.open()
    for t in pages:
        doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 790), t, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_pages_keep_source_and_number():
    pages = read_pdf("a.pdf", make_pdf(["first page text", "second page text"]))
    assert [(p.source, p.page) for p in pages] == [("a.pdf", 1), ("a.pdf", 2)]
    chunks = chunk_pages(pages)
    assert {(c.source, c.page) for c in chunks} == {("a.pdf", 1), ("a.pdf", 2)}
    assert len({c.id for c in chunks}) == len(chunks)


def test_blank_pdf_gives_ocr_message():
    with pytest.raises(PdfError, match="OCR"):
        read_pdf("scan.pdf", make_pdf([""]))


def test_garbage_bytes_give_clear_error():
    with pytest.raises(PdfError):
        read_pdf("x.pdf", b"not a pdf")


def test_encrypted_pdf_rejected():
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "secret")
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    with pytest.raises(PdfError, match="password"):
        read_pdf("e.pdf", data)


def test_chunking_overlap_and_coverage():
    text = " ".join(f"word{i}" for i in range(600))
    chunks = chunk_text(text, size=500, overlap=100)
    assert len(chunks) > 1 and all(len(c) <= 500 for c in chunks)
    assert chunks[0].split()[-1] in chunks[1]  # overlap
    assert "word599" in chunks[-1]


def test_mcqs_from_real_pdf():
    pdf = make_pdf(["Q1. What?\n(A) a\n(B) b\n(C) c\n(D) d\nQ2. Why?\n(A) a\n(B) b\n(C) c\n(D) d\n"
                    "Answer Key\n1. A\n2. B\n3. C\n"])
    qs = parse_mcqs(read_pdf("q.pdf", pdf))
    assert [(q.number, q.answer) for q in qs] == [(1, "A"), (2, "B")]
