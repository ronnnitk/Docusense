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
