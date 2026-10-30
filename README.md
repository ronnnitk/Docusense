# DocuSense AI

Syllabus-driven study assistant. Upload notes, slides and question banks (digital PDFs); ask questions with page-level citations; see which syllabus topics your material covers; practice MCQs and track weak topics. Local-first: Ollama + Sentence Transformers + ChromaDB + SQLite.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull qwen2.5:3b        # needed for Ask / Study guide only
python -m streamlit run app.py   # http://localhost:8501
```

Tests: `pip install -r requirements-dev.txt` then `python -m pytest`.
Demo PDFs: `python scripts/make_sample_pdfs.py` (synthetic, in `data/samples/`).
Retrieval eval: `python scripts/run_eval.py` (edit `eval/eval_set.json` for your own docs).

## Features

| Tab | What it does |
|---|---|
| Documents | Incremental indexing per file (re-uploading replaces only that file), delete a document, MCQ bank preview with extraction warnings |
| Ask | Top-4 retrieval, answer with `[Source n]` citations, expandable source chunks, "not found" without calling the LLM when nothing is close, flags citations to sources that weren't retrieved, optional file filter |
| Quiz | Pick answer -> Check -> locked, scored once, final summary. Randomised, no repeats. Attempts saved to SQLite |
| Syllabus coverage | Paste/upload syllabus -> editable topic list -> Covered / Partially covered / Not found with file + page evidence. Downloadable report |
| Study guide | Cross-document evidence (max 3 chunks per file) -> Markdown guide with citations, conflicts section, Sources list built from metadata. Download .md |
| Progress | Accuracy overall / by topic / by document, review of questions you last got wrong (persists across restarts) |

## Design rules worth knowing

- **Answers are never guessed.** A MCQ is scored only if the PDF has `Answer: B` under it or an "Answer Key" section. Otherwise the choice is recorded but unscored; an on-demand LLM answer is labelled *unverified*.
- Coverage uses retrieval **and** keyword match: a topic is not Covered/Partial unless retrieved chunks contain its key terms.
- Citations are structured metadata (file, page); the LLM's `[Source n]` text is only cross-checked against it.
- PDF text is treated as untrusted data in prompts.

## Layout

`app.py` (UI) · `src/docusense/`: `pdf_ingestion`, `mcq_parser`, `quiz`, `retrieval`, `llm`, `syllabus`, `store`, `schemas` · `tests/` · `scripts/` · `eval/`

## Known limitations

- Digital (selectable-text) PDFs only; scanned PDFs show an OCR-needed message. No PPTX yet.
- MCQ parser expects numbered questions (`Q1.`, `1)`) and lettered options A-E; numbered lists inside a question stem can split it. Check the "flagged for review" list. Quiz answers can't be edited in the app yet.
- Coverage thresholds (`syllabus.py`) and the not-found distance (`llm.py`) are untuned starting values. Verify with the evidence panels on your own material.
- Dense retrieval only (no hybrid/rerank); chunking is character-based.
- Local 3B model is slow (tens of seconds per answer on CPU) and can still paraphrase loosely; always check the cited page.
- Single user; no auth. No difficulty labels (no defensible source for them yet).
- Measured so far: only on 3 synthetic questions (hit@4 3/3). Not a real benchmark.

## Speed notes

- Identical prompts (same question + same retrieved chunks + same model) are served from a persistent SQLite cache (`llm_cache` in `data/docusense.db`), so repeating a question or regenerating a study guide is instant. Changing a document changes the chunks, so it never serves a stale answer.
- Ask and Study guide stream tokens as they are generated; Ollama keeps the model loaded for 30 minutes (`KEEP_ALIVE` in `llm.py`) to skip the reload delay.
- Not used on purpose: Redis, leases/locks and custom tokenization. This is a single-user local app, SQLite already persists the cache, and the model's own tokenizer is handled by Ollama.
- Set `DOCUSENSE_DB=path\to\other.db` to run against a separate database (handy for demos/testing).

## AI-generated practice questions

Quiz page -> "Generate practice questions from my notes". For a topic, the app retrieves chunks and asks the local model for one MCQ per chunk. A question is kept only if (1) the JSON is well-formed with 4 distinct options, (2) the supporting quote it returns really occurs in that chunk, (3) the quote mentions the marked answer, and (4) no wrong option is also supported by the excerpt (checked with a yes/no model call per option). Kept questions are saved with their source page, labelled "AI-generated", and can be excluded from a quiz.

Honest limits: this proves a question is anchored to your text, not that it is perfect. In testing on the sample notes, most first drafts were rejected (several had a second correct option), so expect to try a few chunks and ~20-40 s per question on CPU.
