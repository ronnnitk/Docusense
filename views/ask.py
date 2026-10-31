import time

import streamlit as st

from docusense import llm, retrieval, shared, ui

ui.page_title("Ask", "Cited answers from your own documents.")

sources = shared.indexed_sources()
if not sources:
    st.info("Process some PDFs first (Documents page).")
    st.stop()

chosen = st.multiselect("Search in (empty = all files)", sources)
with st.form("ask_form", border=False):  # a form lets Enter submit the question
    question = st.text_input("What would you like to understand from your PDFs?")
    fresh = st.checkbox("Fresh answer (ignore the saved answer for this exact question)")
    submitted = st.form_submit_button("Ask Docusense")

if submitted and question.strip():
    try:
        t0 = time.perf_counter()
        hits = retrieval.search(
            shared.get_collection(), shared.embedder(), question, 4, chosen or None
        )
        t1 = time.perf_counter()
        if not llm.is_answerable(hits):
            st.warning("This was not found in the uploaded documents.")
        else:
            st.markdown("### Answer")
            answer = st.write_stream(llm.answer_stream(question, hits, fresh=fresh))
            bad = llm.check_citations(answer, len(hits))
            if bad:
                st.warning(
                    f"The model cited source number(s) {bad} "
                    "that were not retrieved - ignore those citations."
                )
            st.caption(f"Retrieval {t1 - t0:.2f}s - total {time.perf_counter() - t0:.2f}s")
        st.markdown("### Retrieved sources")
        for i, h in enumerate(hits, start=1):
            with st.expander(
                f"[Source {i}] {h.source} - page {h.page} (distance {h.distance:.2f})"
            ):
                st.write(h.text)
    except llm.LLMError as err:
        st.error(str(err))
