"""Index data/samples into a throwaway Chroma dir and print retrieval + coverage."""
import sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from docusense import retrieval, syllabus
from docusense.pdf_ingestion import chunk_pages, read_pdf

S = Path(__file__).resolve().parent.parent / "data" / "samples"
emb = retrieval.load_embedder()
col = retrieval.open_collection(tempfile.mkdtemp())
for n in ("ds_notes.pdf", "ds_slides.pdf", "ds_quiz.pdf"):
    retrieval.index_chunks(col, emb, n, chunk_pages(read_pdf(n, (S / n).read_bytes())))
print(retrieval.list_documents(col))
syl = "\n".join(p.text for p in read_pdf("syllabus.pdf", (S / "syllabus.pdf").read_bytes()))
for t in syllabus.parse_topics(syl):
    hits = retrieval.search(col, emb, t, k=6)
    c = syllabus.classify(t, hits)
    print(f"{t:18} {c.status:18} best_dist={hits[0].distance:.2f} files={c.files}")
t0 = time.perf_counter()
h = retrieval.search(col, emb, "Which data structure does BFS use?", 4)
print("search s", round(time.perf_counter() - t0, 3), [(x.source, x.page, round(x.distance, 2)) for x in h])
print("diverse", [(x.source, x.page) for x in retrieval.diverse_search(col, emb, "binary trees", 6)])
retrieval.index_chunks(col, emb, "ds_notes.pdf", [])  # delete one doc only
print("after delete", [d["source"] for d in retrieval.list_documents(col)])
