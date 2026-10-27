"""Quiz session logic: ordering, answer checking, scoring. No LLM, no UI."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .schemas import MCQ


@dataclass(frozen=True)
class Response:
    question_id: str
    selected: str
    correct: str | None        # None = the PDF gave no answer key for this one
    is_correct: bool | None    # None = cannot be checked


@dataclass
class QuizSession:
    mcqs: list[MCQ]
    order: list[int]
    pos: int = 0
    responses: dict[str, Response] = field(default_factory=dict)

    @classmethod
    def new(cls, mcqs: list[MCQ], seed: int | None = None) -> "QuizSession":
        order = list(range(len(mcqs)))
        random.Random(seed).shuffle(order)
        return cls(mcqs=list(mcqs), order=order)

    @property
    def total(self) -> int:
        return len(self.order)

    @property
    def finished(self) -> bool:
        return self.pos >= self.total

    def current(self) -> MCQ | None:
        return None if self.finished else self.mcqs[self.order[self.pos]]

    def response_for_current(self) -> Response | None:
        q = self.current()
        return self.responses.get(q.id) if q else None

    def submit(self, selected: str) -> Response:
        """Lock in an answer for the current question. Scores at most once."""
        q = self.current()
        if q is None:
            raise ValueError("quiz is finished")
        if q.id in self.responses:
            raise ValueError("this question was already answered")
        if selected not in q.options:
            raise ValueError(f"{selected!r} is not an option for this question")
        is_correct = None if q.answer is None else selected == q.answer
        response = Response(q.id, selected, q.answer, is_correct)
        self.responses[q.id] = response
        return response

    def next(self) -> None:
        """Move on. Requires the current question to be answered."""
        if self.finished:
            return
        if self.current().id not in self.responses:
            raise ValueError("answer the question before moving on")
        self.pos += 1

    def summary(self) -> dict:
        checked = [r for r in self.responses.values() if r.is_correct is not None]
        correct = sum(1 for r in checked if r.is_correct)
        return {
            "total": self.total,
            "answered": len(self.responses),
            "scored": len(checked),
            "correct": correct,
            "unscored": len(self.responses) - len(checked),
            "percent": round(100 * correct / len(checked), 1) if checked else None,
        }
