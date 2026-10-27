import pytest

from docusense.quiz import QuizSession
from docusense.schemas import MCQ


def mcq(i, answer="A"):
    return MCQ(f"q{i}", "s.pdf", 1, i, f"stem {i}", {"A": "a", "B": "b"}, answer)


def test_visits_every_question_once():
    qs = [mcq(i) for i in range(6)]
    quiz = QuizSession.new(qs, seed=1)
    seen = []
    while not quiz.finished:
        seen.append(quiz.current().id)
        quiz.submit("A")
        quiz.next()
    assert sorted(seen) == sorted(q.id for q in qs)


def test_scores_once_and_locks_answer():
    quiz = QuizSession.new([mcq(1)], seed=0)
    assert quiz.submit("A").is_correct is True
    with pytest.raises(ValueError):
        quiz.submit("B")
    assert quiz.summary()["correct"] == 1


def test_cannot_skip_unanswered_and_rejects_bad_option():
    quiz = QuizSession.new([mcq(1), mcq(2)], seed=0)
    with pytest.raises(ValueError):
        quiz.next()
    with pytest.raises(ValueError):
        quiz.submit("Z")


def test_questions_without_key_are_unscored():
    quiz = QuizSession.new([mcq(1, answer=None), mcq(2)], seed=0)
    for _ in range(2):
        quiz.submit("A")
        quiz.next()
    s = quiz.summary()
    assert (s["answered"], s["scored"], s["unscored"], s["correct"]) == (2, 1, 1, 1)
    assert s["percent"] == 100.0


def test_five_question_acceptance():
    qs = [mcq(i, answer="A") for i in range(5)]
    quiz = QuizSession.new(qs, seed=3)
    picks = ["A", "B", "A", "B", "A"]
    for p in picks:
        quiz.submit(p)
        quiz.next()
    s = quiz.summary()
    assert quiz.finished and s["correct"] == 3 and s["percent"] == 60.0
