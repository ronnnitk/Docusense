"""Shared data structures."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Page:
    source: str
    page: int
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    page: int


@dataclass(frozen=True)
class Hit:
    """A retrieved chunk. Source/page stay attached as structured data."""
    text: str
    source: str
    page: int
    distance: float  # cosine distance: 0 = identical, larger = less similar


@dataclass
class MCQ:
    id: str
    source: str
    page: int
    number: int
    stem: str
    options: dict[str, str]
    answer: str | None = None       # only set when found in the PDF itself
    explanation: str | None = None  # only set when found in the PDF itself
    issues: list[str] = field(default_factory=list)  # extraction warnings
