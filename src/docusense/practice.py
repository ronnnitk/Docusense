"""Weak-spot practice: pick the questions a student should revisit. No LLM, no UI."""
from __future__ import annotations

from typing import Callable

from .schemas import MCQ

WEAK_ACCURACY = 70.0  # a topic below this accuracy counts as weak


def weak_topics(accuracy_by_topic: list[dict], threshold: float = WEAK_ACCURACY) -> set[str]:
    return {r["name"] for r in accuracy_by_topic if r["accuracy"] < threshold}


def weak_pool(
    bank: list[MCQ],
    latest: dict[str, int],
    weak: set[str],
    topic_of: Callable[[MCQ], str | None],
) -> list[MCQ]:
    """Scorable questions to practise, most urgent first.

    1. Questions whose latest scored attempt was wrong.
    2. Questions in a weak topic that have not yet been answered correctly.
    Questions without an answer key are never included (they cannot be scored).
    """
    wrong, topical = [], []
    for q in bank:
        if not q.answer:
            continue
        if latest.get(q.id) == 0:
            wrong.append(q)
        elif latest.get(q.id) != 1 and weak and topic_of(q) in weak:
            topical.append(q)
    return wrong + topical
