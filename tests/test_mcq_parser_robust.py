"""Real-world layouts that broke (or could break) the first parser."""
from docusense.mcq_parser import parse_mcqs
from docusense.pdf_ingestion import normalize_text, strip_repeated_lines
from docusense.schemas import Page


def pages(*texts, source="t.pdf"):
    return [Page(source, i, t) for i, t in enumerate(texts, start=1)]


def test_running_headers_and_footers_do_not_leak_into_options():
    body = "Q{n}. Question {n}?\n(A) a\n(B) b\n(C) c\n(D) d\n"
    pg = pages(*[
        f"Data Structures Question Bank\n{body.format(n=2*i+1)}{body.format(n=2*i+2)}Page {i+1} of 5\n"
        for i in range(5)
    ])
    qs = parse_mcqs(strip_repeated_lines(pg))
    assert len(qs) == 10
    assert all(q.options["D"] == "d" for q in qs)          # footer not glued to option D
    assert all("Question Bank" not in q.stem for q in qs)


def test_question_split_across_pages_keeps_options():
    qs = parse_mcqs(pages("Q1. Long question here?\n(A) first\n(B) second\n", "(C) third\n(D) fourth\n"))
    assert qs[0].options == {"A": "first", "B": "second", "C": "third", "D": "fourth"}


def test_article_a_in_stem_is_not_an_answer_key_pair():
    # "1. A binary tree ..." must not be read as answer 'A' for question 1
    qs = parse_mcqs(pages(
        "Answers\nsome intro line\n"
        "1. A binary tree has two children?\n(A) yes\n(B) no\n"
        "2. A queue is FIFO?\n(A) yes\n(B) no\n"
        "3. A stack is LIFO?\n(A) yes\n(B) no\n"))
    assert [q.answer for q in qs] == [None, None, None]


def test_key_heading_with_suffix_is_found():
    qs = parse_mcqs(pages("Q1. x?\n(A) a\n(B) b\nQ2. y?\n(A) a\n(B) b\nQ3. z?\n(A) a\n(B) b\n"
                          "ANSWER KEY - Set A\n1. B  2. A  3. B\n"))
    assert [q.answer for q in qs] == ["B", "A", "B"]


def test_inline_answer_lines_are_not_mistaken_for_a_key_heading():
    qs = parse_mcqs(pages("Q1. x?\n(A) a\n(B) b\nAnswer: B\nQ2. y?\n(A) a\n(B) b\nAnswer: A\n"
                          "Q3. z?\n(A) a\n(B) b\nAnswer: A\n"))
    assert [q.answer for q in qs] == ["B", "A", "A"]


def test_numbering_restarts_per_section_key_matched_by_order():
    text = ("Section A\nQ1. a1?\n(A) x\n(B) y\nQ2. a2?\n(A) x\n(B) y\nQ3. a3?\n(A) x\n(B) y\n"
            "Section B\nQ1. b1?\n(A) x\n(B) y\nQ2. b2?\n(A) x\n(B) y\nQ3. b3?\n(A) x\n(B) y\n"
            "Answer Key\n1. A 2. B 3. A\n1. B 2. B 3. B\n")
    qs = parse_mcqs(pages(text))
    assert [q.answer for q in qs] == ["A", "B", "A", "B", "B", "B"]


def test_numeric_parenthesised_options_are_supported():
    qs = parse_mcqs(pages("1. Which is a fruit?\n(1) Car\n(2) Apple\n(3) Desk\n(4) Pen\nAns: (2)\n"
                          "2. Capital of France?\n(1) Rome\n(2) Oslo\n(3) Paris\n(4) Bern\nAns: 3\n"))
    assert qs[0].options == {"A": "Car", "B": "Apple", "C": "Desk", "D": "Pen"}
    assert [q.answer for q in qs] == ["B", "C"]


def test_ligatures_and_soft_hyphens_are_normalised():
    assert normalize_text("the ﬁrst eﬃcient ﬂow") == "the first efficient flow"
    assert normalize_text("exam­ple") == "example"


def test_repeated_lines_stripped_only_when_they_repeat():
    pg = pages("Header\nunique one\nPage 1", "Header\nunique two\nPage 2", "Header\nunique three\nPage 3",
               "Header\nunique four\nPage 4")
    out = strip_repeated_lines(pg)
    assert all("Header" not in p.text and "Page" not in p.text for p in out)
    assert [p.text.strip() for p in out] == ["unique one", "unique two", "unique three", "unique four"]
    short = pages("Header\nonly page")
    assert strip_repeated_lines(short) == short        # too few pages to judge
