"""Generate practice MCQs from document chunks, with grounding checks.

The model is asked for ONE question per chunk plus a quote copied from the chunk
that supports the answer. A question is kept only if:
  * the JSON is well formed with four distinct, non-empty options,
  * the answer letter is one of the options,
  * the quote really occurs in the chunk (so the answer is traceable to the page).
This does not prove the answer is right - it proves the question is anchored to
text in your document. The UI labels these questions as AI-generated.
"""
from __future__ import annotations

import hashlib
import json
import random
import re

from . import llm, syllabus
from .schemas import MCQ, Hit

MIN_QUOTE_CHARS = 20
LETTERS = "ABCD"

_SYSTEM = (
    "You write exam multiple-choice questions for students. "
    + llm._SAFETY +
    "Use ONLY the supplied excerpt. Reply with a single JSON object with keys: "
    '"question" (string), "options" (object with keys A, B, C, D; one correct '
    'answer and three plausible wrong ones), "answer" (the correct letter), '
    '"evidence" (one sentence copied EXACTLY, word for word, from the excerpt '
    "that proves the answer). Test a fact stated in the excerpt."
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_chunk(quote: str, chunk: str) -> bool:
    q = _norm(quote).strip(" .\"'")
    return len(q) >= MIN_QUOTE_CHARS and q in _norm(chunk)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_generated(raw: str, hit: Hit) -> tuple[MCQ | None, str]:
    """Validate model output against its source chunk. Returns (mcq, reason_if_rejected)."""
    data = _extract_json(raw)
    if data is None:
        return None, "not valid JSON"

    stem = str(data.get("question", "")).strip()
    options = data.get("options")
    answer = str(data.get("answer", "")).strip().upper()[:1]
    evidence = str(data.get("evidence", "")).strip()

    if not stem:
        return None, "empty question"
    if not isinstance(options, dict) or sorted(map(str.upper, options)) != list(LETTERS):
        return None, "options are not exactly A-D"
    opts = {str(k).upper(): " ".join(str(v).split()) for k, v in options.items()}
    if any(not v for v in opts.values()) or len({v.lower() for v in opts.values()}) < 4:
        return None, "options are empty or duplicated"
    if answer not in opts:
        return None, "answer is not one of the options"
    if not quote_in_chunk(evidence, hit.text):
        return None, "supporting quote is not in the source text"
    terms = syllabus.key_terms(opts[answer])
    if terms and syllabus.term_overlap(opts[answer], evidence) < 0.34:
        return None, "supporting quote does not mention the answer"

    # models over-pick A/B: shuffle options deterministically and remap the answer
    rng = random.Random(hashlib.sha1(stem.encode()).hexdigest())
    texts = [opts[letter] for letter in LETTERS]
    correct_text = opts[answer]
    rng.shuffle(texts)
    shuffled = dict(zip(LETTERS, texts))
    new_answer = LETTERS[texts.index(correct_text)]

    digest = hashlib.sha1(f"{hit.source}|{hit.page}|{stem}".encode()).hexdigest()[:10]
    return (
        MCQ(
            id=f"gen:{digest}",
            source=hit.source,
            page=hit.page,
            number=0,
            stem=" ".join(stem.split()),
            options=shuffled,
            answer=new_answer,
            explanation=f'Source text: "{" ".join(evidence.split())}" ({hit.source}, p.{hit.page})',
            issues=[],
            generated=True,
        ),
        "",
    )


_VERIFY_SYSTEM = (
    "You check statements against an excerpt. Reply with exactly one word: "
    "SUPPORTED if the excerpt states or clearly implies the statement is true, "
    "otherwise NOT_SUPPORTED."
)


def option_supported(mcq: MCQ, letter: str, hit: Hit) -> bool:
    """True if the excerpt backs this option, i.e. it is not a valid wrong answer."""
    text = mcq.options[letter]
    if quote_in_chunk(text, hit.text):  # copied verbatim from the page
        return True
    reply = llm._chat(
        _VERIFY_SYSTEM,
        "EXCERPT:" + chr(10) + hit.text + chr(10) * 2
        + "QUESTION: " + mcq.stem + chr(10) + "STATEMENT: " + text,
        num_predict=6,
    )
    return reply.strip().upper().startswith("SUPPORTED")


def has_unique_answer(mcq: MCQ, hit: Hit) -> tuple[bool, str]:
    """Reject questions where a supposedly wrong option is also supported by the text."""
    for letter in LETTERS:
        if letter != mcq.answer and option_supported(mcq, letter, hit):
            return False, f"wrong option ({letter}) is also supported by the text"
    return True, ""


def generate_one(hit: Hit, attempts: int = 2, verify: bool = True) -> tuple[MCQ | None, str]:
    """Try up to `attempts` times to get a grounded, unambiguous question from one chunk."""
    reason = "no attempt made"
    for _ in range(attempts):
        raw = llm._chat(
            _SYSTEM,
            "EXCERPT (" + hit.source + ", page " + str(hit.page) + "):" + chr(10) + hit.text,
            num_predict=350,
            json_mode=True,
            temperature=0.5,
        )
        mcq, reason = parse_generated(raw, hit)
        if mcq and verify:
            unique, reason = has_unique_answer(mcq, hit)
            mcq = mcq if unique else None
        if mcq:
            return mcq, ""
    return None, reason
