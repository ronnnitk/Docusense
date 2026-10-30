import json

from docusense import qgen
from docusense.schemas import MCQ, Hit
from docusense.store import Store

CHUNK = ("A binary search tree keeps left < node < right, which makes search, "
         "insertion and deletion O(log n) on average.")
HIT = Hit(CHUNK, "notes.pdf", 3, 0.3)


def raw(**over):
    d = {
        "question": "What is the average cost of search in a balanced BST?",
        "options": {"A": "O(1)", "B": "O(log n)", "C": "O(n)", "D": "O(n^2)"},
        "answer": "B",
        "evidence": "which makes search, insertion and deletion O(log n) on average.",
    }
    d.update(over)
    return json.dumps(d)


def test_valid_question_is_kept_with_provenance():
    mcq, why = qgen.parse_generated(raw(), HIT)
    assert why == "" and mcq.generated and mcq.source == "notes.pdf" and mcq.page == 3
    assert mcq.options[mcq.answer] == "O(log n)"      # answer survives the shuffle
    assert sorted(mcq.options) == list("ABCD")
    assert "notes.pdf, p.3" in mcq.explanation


def test_shuffle_is_deterministic():
    a, _ = qgen.parse_generated(raw(), HIT)
    b, _ = qgen.parse_generated(raw(), HIT)
    assert a.options == b.options and a.id == b.id


def test_quote_not_in_source_is_rejected():
    mcq, why = qgen.parse_generated(raw(evidence="Hash tables give constant time lookup always."), HIT)
    assert mcq is None and "quote" in why


def test_quote_that_does_not_back_the_answer_is_rejected():
    # real quote from the chunk, but about something else than the marked answer
    mcq, why = qgen.parse_generated(
        raw(options={"A": "Uses a stack", "B": "Visits level by level with a queue",
                     "C": "Is always O(n^2)", "D": "Needs recursion"}, answer="B",
            evidence="A binary search tree keeps left < node < right, which makes search"), HIT)
    assert mcq is None and "mention the answer" in why


def test_short_quote_is_rejected():
    mcq, why = qgen.parse_generated(raw(evidence="search"), HIT)
    assert mcq is None and "quote" in why


def test_quote_matching_ignores_case_and_whitespace():
    assert qgen.quote_in_chunk("WHICH makes   search,\ninsertion and deletion O(log n) on average", CHUNK)


def test_bad_shapes_are_rejected():
    assert qgen.parse_generated("not json at all", HIT)[0] is None
    assert qgen.parse_generated(raw(answer="E"), HIT)[0] is None
    assert qgen.parse_generated(raw(options={"A": "x", "B": "y", "C": "z"}), HIT)[0] is None
    dup = {"A": "same", "B": "same", "C": "other", "D": "more"}
    assert qgen.parse_generated(raw(options=dup, answer="A"), HIT)[0] is None
    assert qgen.parse_generated(raw(question=""), HIT)[0] is None


def test_json_wrapped_in_prose_is_still_parsed():
    mcq, _ = qgen.parse_generated("Sure! Here you go:\n" + raw() + "\nHope that helps", HIT)
    assert mcq is not None


def fake_llm(outputs, verdict="NOT_SUPPORTED"):
    gen = iter(outputs)
    return lambda system, user, num_predict, **k: next(gen) if k.get("json_mode") else verdict


def test_generate_one_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(qgen.llm, "_chat", fake_llm(["garbage", raw()]))
    mcq, why = qgen.generate_one(HIT, attempts=2)
    assert mcq is not None and why == ""


def test_question_rejected_when_a_wrong_option_is_also_supported(monkeypatch):
    monkeypatch.setattr(qgen.llm, "_chat", fake_llm([raw(), raw()], verdict="SUPPORTED"))
    mcq, why = qgen.generate_one(HIT, attempts=2)
    assert mcq is None and "also supported" in why


def test_verbatim_copy_of_page_text_is_a_bad_distractor():
    mcq, _ = qgen.parse_generated(raw(options={
        "A": "O(1)", "B": "O(log n)", "C": "O(n)",
        "D": "insertion and deletion O(log n) on average"}), HIT)
    assert qgen.option_supported(mcq, [k for k, v in mcq.options.items() if v.startswith("insertion")][0], HIT)


def test_generate_one_reports_last_reason(monkeypatch):
    monkeypatch.setattr(qgen.llm, "_chat", lambda *a, **k: raw(evidence="made up sentence about nothing at all"))
    mcq, why = qgen.generate_one(HIT, attempts=2)
    assert mcq is None and "quote" in why


def test_store_separates_generated_and_survives_migration(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)   # a database from before the `generated` column
    con.executescript("""CREATE TABLE questions (id TEXT PRIMARY KEY, source TEXT NOT NULL,
        page INTEGER NOT NULL, number INTEGER NOT NULL, stem TEXT NOT NULL, options TEXT NOT NULL,
        answer TEXT, explanation TEXT, issues TEXT NOT NULL DEFAULT '[]');
        INSERT INTO questions VALUES ('x','a.pdf',1,1,'old q','{"A":"1","B":"2"}','A',NULL,'[]');""")
    con.commit(); con.close()

    s = Store(path)
    assert [q.generated for q in s.load_questions()] == [False]
    g, _ = qgen.parse_generated(raw(), HIT)
    s.add_questions([g])
    assert len(s.load_questions(generated=True)) == 1
    assert len(s.load_questions(generated=False)) == 1
    s.replace_questions("a.pdf", [])           # reprocessing a PDF doesn't touch other sources
    assert len(s.load_questions(generated=True)) == 1
