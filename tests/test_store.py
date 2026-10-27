from docusense.schemas import MCQ
from docusense.store import Store


def q(i, ans="A", src="a.pdf"):
    return MCQ(f"{src}{i}", src, 1, i, f"stem {i}", {"A": "x", "B": "y"}, ans)


def test_bank_roundtrip_and_replace(tmp_path):
    s = Store(tmp_path / "t.db")
    s.replace_questions("a.pdf", [q(1), q(2)])
    s.replace_questions("b.pdf", [q(1, src="b.pdf")])
    assert len(s.load_questions()) == 3
    s.replace_questions("a.pdf", [q(3)])
    assert [m.number for m in s.load_questions(["a.pdf"])] == [3]
    s.delete_source("b.pdf")
    assert len(s.load_questions()) == 1


def test_attempts_persist_across_instances_and_analytics(tmp_path):
    path = tmp_path / "t.db"
    s = Store(path)
    qs = [q(1), q(2), q(3, ans=None)]
    s.replace_questions("a.pdf", qs)
    s.record_attempt(qs[0], "A", topic="T1")   # right
    s.record_attempt(qs[1], "B", topic="T1")   # wrong
    s.record_attempt(qs[2], "A", topic="T1")   # unscorable

    s2 = Store(path)  # "restart"
    assert s2.overall() == {"attempts": 2, "correct": 1, "accuracy": 50.0}
    assert s2.accuracy_by("topic")[0]["accuracy"] == 50.0
    wrong = s2.wrong_questions()
    assert [w["number"] for w in wrong] == [2] and wrong[0]["picked"] == "B"


def test_retry_correctly_clears_wrong_list(tmp_path):
    s = Store(tmp_path / "t.db")
    qs = [q(1)]
    s.replace_questions("a.pdf", qs)
    s.record_attempt(qs[0], "B")
    s.record_attempt(qs[0], "A")
    assert s.wrong_questions() == []
