import streamlit as st

from docusense import ingest, shared, ui
from docusense.pdf_ingestion import PdfError

ui.page_title("Documents", "Upload study PDFs, index them, and build your question bank.")

collection, store = shared.get_collection(), shared.get_store()

files = st.file_uploader("Upload study PDFs", type=["pdf"], accept_multiple_files=True)

if st.button("Process PDFs", disabled=not files):
    embedder = shared.embedder()  # only needed once you actually process something
    bar = st.progress(0.0, text="Starting...")
    for n, f in enumerate(files):
        def report(done: int, total: int, n=n, name=f.name) -> None:
            bar.progress((n + done / total) / len(files), text=f"{name}: embedding {done}/{total} chunks")

        try:
            r = ingest.ingest_pdf(
                f.name, f.getvalue(), collection=collection, embedder=embedder, store=store, progress=report
            )
        except PdfError as err:
            st.error(str(err))
            continue
        except Exception as err:  # keep going with the other files; the old version stays intact
            st.error(f"{f.name}: could not be indexed ({type(err).__name__}: {err}).")
            continue
        if r.status == ingest.UNCHANGED:
            st.info(f"{r.name}: already indexed and unchanged - skipped.")
        else:
            verb = "Updated" if r.status == ingest.UPDATED else "Indexed"
            st.success(
                f"{verb} {r.name}: {r.pages} pages, {r.chunks} chunks, "
                f"{r.mcqs} MCQs ({r.with_answer} with an answer in the PDF)."
            )
    bar.empty()

st.subheader("Indexed documents")
docs = store.list_documents()
if not docs:
    st.info("Nothing indexed yet. Upload PDFs and click 'Process PDFs'.")
for d in docs:
    c1, c2 = st.columns([5, 1])
    n_q = len(store.load_questions([d["source"]], generated=False))
    c1.write(f"**{d['source']}** — {d['pages']} pages, {d['chunks']} chunks, {n_q} MCQs")
    if c2.button("Delete", key=f"del_{d['source']}"):
        ingest.remove_document(d["source"], collection=collection, store=store)
        st.rerun()

bank = store.load_questions(generated=False)
if bank:
    with st.expander(f"Question bank preview ({len(bank)} MCQs)"):
        flagged = [q for q in bank if q.issues]
        st.write(
            f"{sum(1 for q in bank if q.answer)} have an answer from the PDF, "
            f"{len(flagged)} flagged for review."
        )
        for q in flagged[:20]:
            st.warning(f"{q.source} p.{q.page} Q{q.number}: {', '.join(q.issues)}")
            st.text(q.stem)
        for q in bank[:5]:
            st.text(f"Q{q.number} ({q.source} p.{q.page}): {q.stem}")
            for k, v in q.options.items():
                st.text(f"   ({k}) {v}")
