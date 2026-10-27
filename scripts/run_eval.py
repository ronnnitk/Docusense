"""Retrieval evaluation: hit@k and latency over eval/eval_set.json.

Indexes data/samples (or --pdf-dir) into a throwaway Chroma dir, so it never
touches your real chroma_db. Add your own questions + expected pages to the JSON.
Usage: python scripts/run_eval.py [--k 4] [--pdf-dir data/samples]
"""
import argparse, json, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from docusense import retrieval
from docusense.pdf_ingestion import chunk_pages, read_pdf

ap = argparse.ArgumentParser()
ap.add_argument("--k", type=int, default=4)
ap.add_argument("--pdf-dir", default=str(ROOT / "data" / "samples"))
ap.add_argument("--eval", default=str(ROOT / "eval" / "eval_set.json"))
args = ap.parse_args()

emb = retrieval.load_embedder()
col = retrieval.open_collection(tempfile.mkdtemp())
for pdf in sorted(Path(args.pdf_dir).glob("*.pdf")):
    retrieval.index_chunks(col, emb, pdf.name, chunk_pages(read_pdf(pdf.name, pdf.read_bytes())))

cases = json.loads(Path(args.eval).read_text(encoding="utf-8"))
hits_ok, times = 0, []
for c in cases:
    t0 = time.perf_counter()
    hits = retrieval.search(col, emb, c["question"], k=args.k)
    times.append(time.perf_counter() - t0)
    ok = any(h.source == c["expected_source"] and h.page in c["expected_pages"] for h in hits)
    hits_ok += ok
    print(("HIT " if ok else "MISS"), c["question"])
print(f"\nhit@{args.k}: {hits_ok}/{len(cases)} = {100*hits_ok/len(cases):.0f}%   "
      f"mean retrieval {1000*sum(times)/len(times):.0f} ms")
