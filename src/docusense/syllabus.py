"""Syllabus topics and coverage. Deterministic: no LLM involved.

A topic is only marked Covered/Partial when retrieved chunks actually contain
the topic's key terms - similarity alone is not enough. Thresholds below are
starting values and have NOT been tuned on real data; adjust using the
coverage evidence shown in the UI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schemas import Hit

COVERED, PARTIAL, NOT_FOUND = "Covered", "Partially covered", "Not found"

STRONG_OVERLAP = 0.6   # share of topic key terms present in the chunk
WEAK_OVERLAP = 0.3
MAX_DISTANCE = 0.65    # cosine distance; larger = unrelated
MIN_STRONG_FOR_COVERED = 2

STOPWORDS = frozenset(
    "the and for with from into that this are was were its their his her our "
    "about over under between using use used via per of in on to a an is as "
    "by or at be it basic basics introduction overview concept concepts "
    "types type".split()
)
_UNIT_RE = re.compile(r"(?i)^(?:unit|module|chapter|section|part)\b[\s\d.ivx]*[:\-–.]?\s*")
_BULLET_RE = re.compile(r"^\s*(?:[-*•▪●◦]+|\(?\d{1,2}[.)]|\(?[a-z][.)])\s+")


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]  # trees -> tree
    return token[:5]


def key_terms(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9+#]+", text.lower())
    return {_stem(t) for t in tokens if len(t) >= 3 and t not in STOPWORDS}


def parse_topics(text: str) -> list[str]:
    """Turn pasted/uploaded syllabus text into a de-duplicated topic list.

    One topic per line. A heading like `Unit 2: Sorting, Searching; Hashing`
    becomes three topics. The result is meant to be edited by the user.
    """
    topics, seen = [], set()
    for raw in text.splitlines():
        line = _BULLET_RE.sub("", raw.strip()).strip(" \t.:;-–")
        if not line:
            continue
        has_unit = bool(_UNIT_RE.match(line))
        line = _UNIT_RE.sub("", line).strip()
        parts = re.split(r"[;,]", line) if (has_unit or ";" in line) else [line]
        for part in parts:
            part = part.strip(" \t.:;-–")
            if len(part) < 3 or not key_terms(part):
                continue
            if part.lower() not in seen:
                seen.add(part.lower())
                topics.append(part)
    return topics


@dataclass
class Evidence:
    hit: Hit
    overlap: float


@dataclass
class TopicCoverage:
    topic: str
    status: str
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def files(self) -> list[str]:
        return sorted({e.hit.source for e in self.evidence})


def term_overlap(topic: str, text: str) -> float:
    terms = key_terms(topic)
    if not terms:
        return 0.0
    return len(terms & key_terms(text)) / len(terms)


def classify(topic: str, hits: list[Hit]) -> TopicCoverage:
    evidence = [
        Evidence(h, term_overlap(topic, h.text))
        for h in hits
        if h.distance <= MAX_DISTANCE
    ]
    evidence = [e for e in evidence if e.overlap >= WEAK_OVERLAP]
    evidence.sort(key=lambda e: (-e.overlap, e.hit.distance))
    strong = [e for e in evidence if e.overlap >= STRONG_OVERLAP]

    if len(strong) >= MIN_STRONG_FOR_COVERED:
        status = COVERED
    elif evidence:
        status = PARTIAL
    else:
        status = NOT_FOUND
    return TopicCoverage(topic, status, evidence[:4])


def assign_topic(text: str, topics: list[str]) -> str | None:
    """Best matching topic for a piece of text (e.g. a quiz question)."""
    best, best_score = None, 0.5
    for topic in topics:
        score = term_overlap(topic, text)
        if score > best_score:
            best, best_score = topic, score
    return best
