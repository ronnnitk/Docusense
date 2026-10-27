"""Extract MCQs (and answers, only if the PDF contains them) from page text.

Handles question starts like `Q35.`, `35)`, `Question 4:` and options like
`(A)`, `A)`, `A.`, `a)`, including all options on one line `(A) x (B) y`.
Answers are read from `Answer: B` lines inside a question or from a trailing
"Answer Key" section. If neither exists, `answer` stays None - it is never
guessed.
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
INLINE_ANSWER_RE = re.compile(
    r"(?im)^[ \t]*(?:correct[ \t]+)?(?:answer|ans)\b[ \t]*[:\-=]?[ \t]*\(?([A-Ea-e])\)?(?![A-Za-z])"
)
EXPLANATION_RE = re.compile(r"(?is)explanation[ \t]*[:\-][ \t]*(.*)")
KEY_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:answer[ \t]*keys?|answers?|solutions?)[ \t]*:?[ \t]*$"
)
KEY_PAIR_RE = re.compile(
    r"(?i)(?:^|[\s,;])(?:Q\s*)?(\d{1,3})[ \t]*[-.:)=][ \t]*\(?([A-E])\)?(?![A-Za-z])"
)


def _find_answer_key(text: str) -> tuple[int, dict[int, str]]:
    """Return (offset where the key section starts, {question number: letter})."""
    for heading in reversed(list(KEY_HEADING_RE.finditer(text))):
        pairs = KEY_PAIR_RE.findall(text[heading.end():])
        if len(pairs) >= 3:
            return heading.start(), {int(n): letter.upper() for n, letter in pairs}
    return len(text), {}


def _split_options(block: str) -> tuple[str, dict[str, str]]:
    """Split a question block into (stem, {letter: text})."""
    matches = list(OPTION_LINE_RE.finditer(block))
    if len(matches) < 2:
        matches = list(OPTION_INLINE_RE.finditer(block))
    # keep the consecutive run A, B, C, ... starting at A
    run = []
    for m in matches:
        if m.group(1).upper() == chr(ord("A") + len(run)):
            run.append(m)
    if len(run) < 2:
        return block.strip(), {}

    stem = block[: run[0].start()].strip()
    options = {}
    for i, m in enumerate(run):
        end = run[i + 1].start() if i + 1 < len(run) else len(block)
        options[m.group(1).upper()] = " ".join(block[m.end():end].split())
    return stem, options


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

    key_start, key = _find_answer_key(text)
    body = text[:key_start]

    matches = list(QUESTION_RE.finditer(body))
    mcqs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]

        answer = explanation = None
        ans = INLINE_ANSWER_RE.search(block)
        if ans:
            answer = ans.group(1).upper()
            exp = EXPLANATION_RE.search(block[ans.end():])
            explanation = " ".join(exp.group(1).split()) if exp else None
            block = block[: ans.start()]

        stem, options = _split_options(block)
        if len(options) < 2:
            continue  # not an MCQ

        number = int(m.group(1))
        if answer is None:
            answer = key.get(number)

        stem = " ".join(stem.split())
        issues = []
        if not stem:
            issues.append("empty question text")
        if len(options) < 4:
            issues.append(f"only {len(options)} options found")
        if answer and answer not in options:
            issues.append(f"answer {answer} is not one of the options")
            answer = None

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
    return mcqs
