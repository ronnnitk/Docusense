from docusense import practice
from docusense.schemas import MCQ
from docusense.store import Store


def mcq(i, answer="A"):
    return MCQ(f"q{i}", "a.pdf", 1, i, f"stem {i}", {"A": "x", "B": "y"}, answer, None, [])


def test_wrong_first_then_weak_topic_unseen_and_skips_correct_and_unscored():
    bank = [mcq(1), mcq(2), mcq(3), mcq(4), mcq(5, answer=None)]
    latest = {"q1": 0, "q2": 1}
    topic_of = lambda q: "trees" if q.id in ("q2", "q3", "q5") else "other"
    pool = practice.weak_pool(bank, latest, {"trees"}, topic_of)
    assert [q.id for q in pool] == ["q1", "q3"]  # q2 already correct, q4 other topic, q5 no key


def test_weak_topics_threshold():
    rows = [{"name": "a", "accuracy": 40.0}, {"name": "b", "accuracy": 90.0}]
    assert practice.weak_topics(rows) == {"a"}


def test_store_latest_results_uses_most_recent_attempt():
    s = Store(":memory:")
    q = mcq(1)
    s.record_attempt(q, "B")  # wrong
    s.record_attempt(q, "A")  # then right
    s.record_attempt(mcq(2), "B")
    assert s.latest_results() == {"q1": 1, "q2": 0}
