"""PDF text extraction and chunking. Keeps file name + page on everything."""
from __future__ import annotations

import re

import pymupdf

from .schemas import Chunk, Page

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


class PdfError(Exception):
    """A PDF could not be used; the message is safe to show to the user."""


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    # "inter-\nnational" -> "international" (lowercase both sides only, so
    # option lists like "A-\nB" are left alone)
    return re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)


def read_pdf(name: str, data: bytes) -> list[Page]:
    """Return one Page per page that has selectable text."""
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfError(f"{name}: could not open this file as a PDF ({exc}).") from exc

    try:
        if pdf.needs_pass:
            raise PdfError(f"{name}: the PDF is password-protected.")
        pages = []
        for number, page in enumerate(pdf, start=1):
            text = normalize_text(page.get_text("text")).strip()
            if text:
                pages.append(Page(source=name, page=number, text=text))
    finally:
        pdf.close()

    if not pages:
        raise PdfError(
            f"{name}: no selectable text found. It is probably a scanned PDF "
            "and needs OCR, which is not supported yet."
        )
    return pages


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # prefer to cut at whitespace within the last 100 chars
            cut = text.rfind(" ", max(start, end - 100), end)
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    chunks = []
    for page in pages:
        for n, piece in enumerate(chunk_text(page.text)):
            chunks.append(
                Chunk(
                    id=f"{page.source}_{page.page}_{n}",
                    text=piece,
                    source=page.source,
                    page=page.page,
                )
            )
    return chunks
