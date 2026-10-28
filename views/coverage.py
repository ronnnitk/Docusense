import streamlit as st

from docusense import retrieval, shared, syllabus, ui
from docusense.pdf_ingestion import PdfError, read_pdf

ui.page_title("Syllabus coverage", "See which syllabus topics your documents actually cover.")

embedder, collection = shared.get_embedder(), shared.get_collection()
ss = st.session_state

st.write("Paste a syllabus (or upload a PDF), extract topics, edit them, then check coverage.")
syl_pdf = st.file_uploader("Syllabus PDF (optional, not indexed)", type=["pdf"], key="syl_pdf")
raw = st.text_area("Syllabus text", height=150, key="syl_raw")

if st.button("Extract topics"):
    text = raw
    if syl_pdf is not None:
        try:
            text = "\n".join(p.text for p in read_pdf(syl_pdf.name, syl_pdf.getvalue()))
        except PdfError as err:
            st.error(str(err))
    ss.topics_text = "\n".join(syllabus.parse_topics(text))
    ss.topics_widget = ss.topics_text
    ss.coverage = None
    st.rerun()


def _sync_topics() -> None:
    # widget state is dropped when you leave this page; topics_text survives
    ss.topics_text = ss.topics_widget


if "topics_widget" not in ss:
    ss.topics_widget = ss.topics_text
st.text_area(
    "Topics (one per line - edit freely)", height=200, key="topics_widget", on_change=_sync_topics
)

if st.button("Check coverage", disabled=not shared.topics() or not shared.indexed_sources()):
    with st.spinner("Matching topics against your documents..."):
        ss.coverage = [
            syllabus.classify(t, retrieval.search(collection, embedder, t, k=6))
            for t in shared.topics()
        ]

if ss.coverage:
    counts = {s: sum(c.status == s for c in ss.coverage)
              for s in (syllabus.COVERED, syllabus.PARTIAL, syllabus.NOT_FOUND)}
    for col, (name, n) in zip(st.columns(3), counts.items()):
        col.metric(name, n)
    icon = {syllabus.COVERED: "🟢", syllabus.PARTIAL: "🟡", syllabus.NOT_FOUND: "🔴"}
    for c in ss.coverage:
        files_txt = ", ".join(c.files) or "no supporting material"
        with st.expander(f"{icon[c.status]} {c.topic} — {c.status} ({files_txt})"):
            if not c.evidence:
                st.write("No retrieved chunk contained this topic's key terms.")
            for e in c.evidence:
                st.markdown(
                    f"**{e.hit.source}, page {e.hit.page}** "
                    f"(term match {e.overlap:.0%}, distance {e.hit.distance:.2f})"
                )
                st.write(e.hit.text)
    md = "| Topic | Status | Evidence |\n|---|---|---|\n" + "\n".join(
        f"| {c.topic} | {c.status} | "
        + "; ".join(f"{e.hit.source} p.{e.hit.page}" for e in c.evidence) + " |"
        for c in ss.coverage
    )
    st.download_button("Download coverage report (.md)", md, "coverage.md")
