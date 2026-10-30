import streamlit as st

from docusense import retrieval, shared, ui
from docusense.mcq_parser import parse_mcqs
from docusense.pdf_ingestion import PdfError, chunk_pages, read_pdf

ui.page_title("Documents", "Upload study PDFs, index them, and build your question bank.")

embedder, collection, store = shared.get_embedder(), shared.get_collection(), shared.get_store()

files = st.file_uploader("Upload study PDFs", type=["pdf"], accept_multiple_files=True)

if st.button("Process PDFs", disabled=not files):
    with st.spinner("Reading PDFs and creating embeddings..."):
        for f in files:
            try:
                pages = read_pdf(f.name, f.getvalue())
            except PdfError as err:
                st.error(str(err))
                continue
            chunks = chunk_pages(pages)
            retrieval.index_chunks(collection, embedder, f.name, chunks)
            mcqs = parse_mcqs(pages)
            store.replace_questions(f.name, mcqs)
            with_key = sum(1 for q in mcqs if q.answer)
            st.success(
                f"{f.name}: {len(pages)} pages, {len(chunks)} chunks, "
                f"{len(mcqs)} MCQs ({with_key} with an answer in the PDF)."
            )

st.subheader("Indexed documents")
docs = retrieval.list_documents(collection)
if not docs:
    st.info("Nothing indexed yet. Upload PDFs and click 'Process PDFs'.")
for d in docs:
    c1, c2 = st.columns([5, 1])
    n_q = len(store.load_questions([d["source"]], generated=False))
    c1.write(f"**{d['source']}** — {d['pages']} pages, {d['chunks']} chunks, {n_q} MCQs")
    if c2.button("Delete", key=f"del_{d['source']}"):
        retrieval.delete_document(collection, d["source"])
        store.delete_source(d["source"])
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
