"""PDF text extraction and chunking. Keeps file name + page on everything."""
from __future__ import annotations

import re

import pymupdf

from .schemas import Chunk, Page

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


class PdfError(Exception):
    """A PDF could not be used; the message is safe to show to the user."""


_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").replace("\xad", "")
    for ligature, plain in _LIGATURES.items():  # PDFs often store "fi" as one glyph, breaking matching
        text = text.replace(ligature, plain)
    # "inter-\nnational" -> "international" (lowercase both sides only, so
    # option lists like "A-\nB" are left alone)
    return re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)


# lines that look like question/option markers are content, never boilerplate
_CONTENT_LINE = re.compile(r"^\s*(?:\(?[A-Ea-e1-5][.)]|\([A-Ea-e1-5]\)|Q?\s*\d{1,3}\s*[.):])\s*\S")


def _shape(line: str) -> str:
    return re.sub(r"\d+", "#", " ".join(line.lower().split()))


def _edge_lines(text: str) -> set[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return {*lines[:2], *lines[-2:]}


def strip_repeated_lines(pages: list[Page], min_pages: int = 4, share: float = 0.6) -> list[Page]:
    """Drop running headers/footers (e.g. 'Question Bank', 'Page 3 of 10').

    Only the first/last two lines of a page are considered, digits are ignored
    when comparing, and a line must recur on >= `share` of the pages. Option and
    question lines are never removed.
    """
    if len(pages) < min_pages:
        return pages

    def candidate(line: str) -> bool:
        return len(line.strip()) <= 80 and not _CONTENT_LINE.match(line)

    seen: dict[str, int] = {}
    for page in pages:
        for shape in {_shape(ln) for ln in _edge_lines(page.text) if candidate(ln)}:
            seen[shape] = seen.get(shape, 0) + 1
    boiler = {shape for shape, n in seen.items() if n >= max(min_pages, share * len(pages))}
    if not boiler:
        return pages

    cleaned = []
    for page in pages:
        edges = _edge_lines(page.text)
        kept = [
            ln for ln in page.text.splitlines()
            if not (ln in edges and candidate(ln) and _shape(ln) in boiler)
        ]
        text = "\n".join(kept).strip()
        if text:
            cleaned.append(Page(page.source, page.page, text))
    return cleaned


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
    return strip_repeated_lines(pages) or pages


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
