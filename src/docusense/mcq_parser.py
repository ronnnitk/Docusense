"""Extract MCQs (and answers, only if the PDF contains them) from page text.

Handles question starts like `Q35.`, `35)`, `Question 4:` and options like
`(A)`, `A)`, `A.`, `a)`, `(1)`..`(4)` (stored as A..D), including all options on
one line. Answers are read from `Answer: B` lines inside a question or from a
trailing "Answer Key" section. If neither exists - or the key is ambiguous -
`answer` stays None: it is never guessed.
"""
from __future__ import annotations

import hashlib
import re
from bisect import bisect_right

from .schemas import MCQ, Page

QUESTION_RE = re.compile(
    r"(?im)^[ \t]*(?:Q(?:uestion)?\.?[ \t]*)?(\d{1,3})[ \t]*[.)\]:][ \t]*(?=\S)"
)
OPTION_LINE_RE = re.compile(r"(?m)^[ \t]*\(?([A-Ea-e])[.)][ \t]*(?=\S)")
OPTION_INLINE_RE = re.compile(r"\(([A-Ea-e])\)[ \t]*")
NUM_OPTION_LINE_RE = re.compile(r"(?m)^[ \t]*\(([1-5])\)[ \t]*(?=\S)")
NUM_OPTION_INLINE_RE = re.compile(r"\(([1-5])\)[ \t]*")
INLINE_ANSWER_RE = re.compile(
    r"(?im)^[ \t]*(?:correct[ \t]+)?(?:answer|ans)\b[ \t]*[:\-=.]?[ \t]*\(?([A-Ea-e1-5])\)?(?![A-Za-z0-9])"
)
EXPLANATION_RE = re.compile(r"(?is)explanation[ \t]*[:\-][ \t]*(.*)")
# "Answers", "Answer Key", "ANSWER KEY - Set A" ... but NOT an inline "Answer: B" / "Ans B"
KEY_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:answer[ \t]*keys?|answers?|solutions?)\b"
    r"(?![ \t]*[:\-=.]?[ \t]*\(?[A-Ea-e1-5]\)?(?![A-Za-z0-9]))[^\n]{0,40}$"
)
# "1. B", "2-A", "3) (c)", "Q4: D" - the letter must end the entry, so a stem like
# "1. A binary tree ..." is never read as the pair (1, A).
KEY_PAIR_RE = re.compile(
    r"(?im)(?:^|[\s,;])(?:Q[ \t]*)?(\d{1,3})[ \t]*[-.:)=][ \t]*\(?([A-E1-5])\)?"
    r"(?=[ \t]*(?:$|[,;]|(?:Q[ \t]*)?\d{1,3}[ \t]*[-.:)=]))"
)


def _to_letter(token: str) -> str:
    return chr(64 + int(token)) if token.isdigit() else token.upper()


def _find_answer_key(text: str) -> tuple[int, list[tuple[int, str]]]:
    """Return (offset where the key section starts, [(question number, letter), ...])."""
    for heading in reversed(list(KEY_HEADING_RE.finditer(text))):
        pairs = [(int(n), _to_letter(a)) for n, a in KEY_PAIR_RE.findall(text[heading.end():])]
        if len(pairs) >= 3:
            return heading.start(), pairs
    return len(text), []


def _consecutive_run(matches, to_index) -> list:
    """The leading run of matches whose markers go A,B,C... (or 1,2,3...)."""
    run = []
    for m in matches:
        if to_index(m.group(1)) == len(run):
            run.append(m)
    return run


def _split_options(block: str) -> tuple[str, dict[str, str]]:
    """Split a question block into (stem, {letter: text})."""
    letter = lambda c: ord(c.upper()) - 65  # noqa: E731
    digit = lambda c: int(c) - 1  # noqa: E731
    for line_re, inline_re, to_index in (
        (OPTION_LINE_RE, OPTION_INLINE_RE, letter),
        (NUM_OPTION_LINE_RE, NUM_OPTION_INLINE_RE, digit),
    ):
        run = _consecutive_run(list(line_re.finditer(block)), to_index)
        if len(run) < 2:
            run = _consecutive_run(list(inline_re.finditer(block)), to_index)
        if len(run) >= 2:
            break
    else:
        return block.strip(), {}

    stem = block[: run[0].start()].strip()
    options = {}
    for i, m in enumerate(run):
        end = run[i + 1].start() if i + 1 < len(run) else len(block)
        options[chr(65 + i)] = " ".join(block[m.end():end].split())
    return stem, options


def _assign_key(mcqs: list[MCQ], pairs: list[tuple[int, str]]) -> None:
    """Fill `answer` from a trailing key, but only when the match is unambiguous."""
    if not pairs:
        return
    if [n for n, _ in pairs] == [q.number for q in mcqs]:
        for q, (_, letter) in zip(mcqs, pairs):  # same order, e.g. numbering restarts per section
            q.answer = q.answer or letter
        return
    by_number: dict[int, set[str]] = {}
    for n, letter in pairs:
        by_number.setdefault(n, set()).add(letter)
    counts = {n: 0 for n in by_number}
    for q in mcqs:
        counts[q.number] = counts.get(q.number, 0) + 1
    for q in mcqs:
        letters = by_number.get(q.number)
        # ambiguous: the key disagrees with itself, or several questions share this number
        if letters and len(letters) == 1 and counts[q.number] == 1 and not q.answer:
            q.answer = next(iter(letters))


def parse_mcqs(pages: list[Page]) -> list[MCQ]:
    """Parse MCQs from the pages of ONE source file."""
    if not pages:
        return []
    source = pages[0].source

    text = ""
    starts = []  # offset where each page's text begins
    for p in pages:
        starts.append(len(text))
        text += p.text + "\n"
    page_numbers = [p.page for p in pages]

    key_start, key_pairs = _find_answer_key(text)
    body = text[:key_start]

    matches = list(QUESTION_RE.finditer(body))
    mcqs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]

        answer = explanation = None
        ans = INLINE_ANSWER_RE.search(block)
        if ans:
            answer = _to_letter(ans.group(1))
            exp = EXPLANATION_RE.search(block[ans.end():])
            explanation = " ".join(exp.group(1).split()) if exp else None
            block = block[: ans.start()]

        stem, options = _split_options(block)
        if len(options) < 2:
            continue  # not an MCQ

        number = int(m.group(1))
        stem = " ".join(stem.split())
        issues = []
        if not stem:
            issues.append("empty question text")
        if len(options) < 4:
            issues.append(f"only {len(options)} options found")

        page = page_numbers[max(bisect_right(starts, m.start()) - 1, 0)]
        digest = hashlib.sha1(f"{source}|{number}|{stem}".encode()).hexdigest()[:10]
        mcqs.append(
            MCQ(
                id=f"{source}:{number}:{digest}",
                source=source,
                page=page,
                number=number,
                stem=stem,
                options=options,
                answer=answer,
                explanation=explanation,
                issues=issues,
            )
        )

    _assign_key(mcqs, key_pairs)
    for q in mcqs:
        if q.answer and q.answer not in q.options:
            q.issues.append(f"answer {q.answer} is not one of the options")
            q.answer = None
    return mcqs
