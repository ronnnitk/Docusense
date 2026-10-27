from docusense.mcq_parser import parse_mcqs
from docusense.schemas import Page


def pages(*texts, source="t.pdf"):
    return [Page(source, i, t) for i, t in enumerate(texts, start=1)]


def test_paren_options_and_page_numbers():
    p = pages(
        "Q1. What is 2+2?\n(A) 3\n(B) 4\n(C) 5\n(D) 6\n",
        "Q2) Capital of France?\n(A) Rome\n(B) Paris\n(C) Oslo\n(D) Bern\n",
    )
    qs = parse_mcqs(p)
    assert [q.number for q in qs] == [1, 2]
    assert [q.page for q in qs] == [1, 2]
    assert qs[0].options == {"A": "3", "B": "4", "C": "5", "D": "6"}
    assert qs[0].stem == "What is 2+2?"
    assert qs[0].answer is None and qs[0].issues == []


def test_other_option_formats_and_multiline():
    qs = parse_mcqs(pages(
        "1. Which is a fruit that is\nreally long text?\nA. Apple\nB. Car\nC. Desk\nD. Pen\n"
        "2) Pick one\na) x\nb) y\n"
    ))
    assert len(qs) == 2
    assert qs[0].stem == "Which is a fruit that is really long text?"
    assert qs[1].options == {"A": "x", "B": "y"}
    assert qs[1].issues == ["only 2 options found"]


def test_inline_options_on_one_line():
    qs = parse_mcqs(pages("Q5. Sky colour? (A) red (B) blue (C) green (D) pink\n"))
    assert qs[0].options["B"] == "blue"


def test_non_mcq_numbered_text_is_ignored():
    assert parse_mcqs(pages("1. Introduction\nsome text\n2. Methods\nmore text\n")) == []


def test_inline_answer_and_explanation():
    qs = parse_mcqs(pages(
        "Q1. x?\n(A) a\n(B) b\n(C) c\n(D) d\nAnswer: B\nExplanation: because b.\n"
        "Q2. y?\n(A) a\n(B) b\n(C) c\n(D) d\nAns: (C)\n"
    ))
    assert qs[0].answer == "B" and qs[0].explanation == "because b."
    assert qs[0].options["D"] == "d"  # answer line not glued to last option
    assert qs[1].answer == "C"


def test_trailing_answer_key_across_pages():
    qs = parse_mcqs(pages(
        "Q1. x?\n(A) a\n(B) b\n(C) c\n(D) d\nQ2. y?\n(A) a\n(B) b\n(C) c\n(D) d\n",
        "Answer Key\n1. C\n2-A\n3) D\n",
    ))
    assert [q.answer for q in qs] == ["C", "A"]
    assert qs[1].options["D"] == "d"


def test_no_answer_key_means_no_answer():
    qs = parse_mcqs(pages("Q1. x?\n(A) a\n(B) b\n"))
    assert qs[0].answer is None


def test_answer_not_in_options_is_dropped_and_flagged():
    qs = parse_mcqs(pages("Q1. x?\n(A) a\n(B) b\nAnswer: D\n"))
    assert qs[0].answer is None
    assert any("not one of the options" in i for i in qs[0].issues)


def test_ids_are_stable_and_unique():
    text = "Q1. x?\n(A) a\n(B) b\nQ2. y?\n(A) a\n(B) b\n"
    a, b = parse_mcqs(pages(text)), parse_mcqs(pages(text))
    assert [q.id for q in a] == [q.id for q in b]
    assert len({q.id for q in a}) == 2
