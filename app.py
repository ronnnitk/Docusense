import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st  # noqa: E402

from docusense import llm, retrieval, syllabus  # noqa: E402
from docusense.mcq_parser import parse_mcqs  # noqa: E402
from docusense.pdf_ingestion import PdfError, chunk_pages, read_pdf  # noqa: E402
from docusense.quiz import QuizSession  # noqa: E402
from docusense.store import Store  # noqa: E402

st.set_page_config(page_title="DocuSense AI", page_icon="📚", layout="wide")
st.title("📚 DocuSense AI")
st.caption("Syllabus-driven study assistant: cited answers, coverage map, MCQ practice.")


@st.cache_resource
def get_embedder():
    return retrieval.load_embedder()


@st.cache_resource
def get_collection():
    return retrieval.open_collection()


@st.cache_resource
def get_store():
    return Store()


embedder, collection, store = get_embedder(), get_collection(), get_store()
ss = st.session_state
ss.setdefault("topics_text", "")
ss.setdefault("coverage", None)

tab_docs, tab_ask, tab_quiz, tab_syl, tab_guide, tab_prog = st.tabs(
    ["Documents", "Ask", "Quiz", "Syllabus coverage", "Study guide", "Progress"]
)


def indexed_sources() -> list[str]:
    return [d["source"] for d in retrieval.list_documents(collection)]


def topics() -> list[str]:
    return [t.strip() for t in ss.topics_text.splitlines() if t.strip()]


# ---------------------------------------------------------------- Documents
with tab_docs:
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
        n_q = len(store.load_questions([d["source"]]))
        c1.write(f"**{d['source']}** — {d['pages']} pages, {d['chunks']} chunks, {n_q} MCQs")
        if c2.button("Delete", key=f"del_{d['source']}"):
            retrieval.delete_document(collection, d["source"])
            store.delete_source(d["source"])
            st.rerun()

    bank = store.load_questions()
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

# ---------------------------------------------------------------------- Ask
with tab_ask:
    sources = indexed_sources()
    if not sources:
        st.info("Process some PDFs first.")
    else:
        chosen = st.multiselect("Search in (empty = all files)", sources)
        question = st.text_input("What would you like to understand from your PDFs?")
        if st.button("Ask DocuSense") and question.strip():
            try:
                with st.spinner("Searching and generating answer..."):
                    t0 = time.perf_counter()
                    hits = retrieval.search(collection, embedder, question, 4, chosen or None)
                    t1 = time.perf_counter()
                    result = llm.answer_question(question, hits)
                    t2 = time.perf_counter()
                if result.answerable:
                    st.markdown("### Answer")
                    st.write(result.text)
                    if result.invalid_citations:
                        st.warning(
                            f"The model cited source number(s) {result.invalid_citations} "
                            "that were not retrieved - ignore those citations."
                        )
                else:
                    st.warning(result.text)
                st.caption(f"Retrieval {t1 - t0:.2f}s · generation {t2 - t1:.2f}s")
                st.markdown("### Retrieved sources")
                for i, h in enumerate(result.hits, start=1):
                    with st.expander(
                        f"[Source {i}] {h.source} — page {h.page} (distance {h.distance:.2f})"
                    ):
                        st.write(h.text)
            except llm.LLMError as err:
                st.error(str(err))

# --------------------------------------------------------------------- Quiz
with tab_quiz:
    bank = store.load_questions()
    if not bank:
        st.info("No MCQs yet. Process PDFs that contain multiple-choice questions.")
    else:
        quiz: QuizSession | None = ss.get("quiz")

        if quiz is None:
            files_with_q = sorted({q.source for q in bank})
            picked = st.multiselect("Practice from", files_with_q, default=files_with_q)
            only_key = st.checkbox(
                "Only questions with an answer in the PDF (scored)", value=True
            )
            pool = [
                q for q in bank
                if q.source in picked and (q.answer or not only_key)
            ]
            st.write(f"{len(pool)} questions available.")
            if st.button("Start quiz", disabled=not pool):
                ss.quiz = QuizSession.new(pool)
                ss.pop("provisional", None)
                st.rerun()
        else:
            q = quiz.current()
            if q is None:
                s = quiz.summary()
                st.success("Quiz complete!")
                if s["scored"]:
                    st.metric("Score", f"{s['correct']} / {s['scored']}", f"{s['percent']}%")
                if s["unscored"]:
                    st.info(f"{s['unscored']} question(s) had no answer key and were not scored.")
                if st.button("Restart quiz"):
                    del ss["quiz"]
                    st.rerun()
            else:
                resp = quiz.response_for_current()
                st.subheader(f"Question {quiz.pos + 1} of {quiz.total}")
                st.caption(f"{q.source} · page {q.page} · Q{q.number}")
                st.write(q.stem)
                choice = st.radio(
                    "Options",
                    list(q.options),
                    index=None,
                    format_func=lambda k: f"({k}) {q.options[k]}",
                    key=f"sel_{q.id}",
                    disabled=resp is not None,
                    label_visibility="collapsed",
                )

                if resp is None:
                    if st.button("Check answer", disabled=choice is None):
                        r = quiz.submit(choice)
                        store.record_attempt(q, choice, syllabus.assign_topic(
                            q.stem + " " + " ".join(q.options.values()), topics()))
                        st.rerun()
                else:
                    if resp.is_correct is None:
                        st.info(
                            "This PDF has no answer for this question, so it is not "
                            "scored. Your choice was recorded."
                        )
                        if st.button("Ask AI for a provisional answer"):
                            try:
                                ss.provisional = (q.id, llm.provisional_mcq_answer(q.stem, q.options))
                            except llm.LLMError as err:
                                st.error(str(err))
                        if ss.get("provisional", (None,))[0] == q.id:
                            st.warning("Unverified AI guess: " + ss.provisional[1])
                    elif resp.is_correct:
                        st.success(f"Correct! ({resp.correct})")
                    else:
                        st.error(f"Wrong. You chose ({resp.selected}); correct is ({resp.correct}).")
                    if q.explanation:
                        st.caption("Explanation (from the PDF): " + q.explanation)

                    last = quiz.pos + 1 == quiz.total
                    if st.button("Finish" if last else "Next question"):
                        quiz.next()
                        st.rerun()

                s = quiz.summary()
                st.sidebar.metric("Quiz score", f"{s['correct']} / {s['scored']}")
                if st.button("Quit quiz"):
                    del ss["quiz"]
                    st.rerun()

# ---------------------------------------------------------------- Syllabus
with tab_syl:
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
        ss.coverage = None
        st.rerun()

    st.text_area("Topics (one per line - edit freely)", height=200, key="topics_text")

    if st.button("Check coverage", disabled=not topics() or not indexed_sources()):
        with st.spinner("Matching topics against your documents..."):
            ss.coverage = [
                syllabus.classify(t, retrieval.search(collection, embedder, t, k=6))
                for t in topics()
            ]

    if ss.coverage:
        counts = {s: sum(c.status == s for c in ss.coverage)
                  for s in (syllabus.COVERED, syllabus.PARTIAL, syllabus.NOT_FOUND)}
        m = st.columns(3)
        for col, (name, n) in zip(m, counts.items()):
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

# ------------------------------------------------------------- Study guide
with tab_guide:
    opts = topics()
    topic = st.selectbox("Pick a syllabus topic", opts) if opts else None
    custom = st.text_input("...or type any topic", value="")
    topic = custom.strip() or topic
    if st.button("Generate study guide", disabled=not topic or not indexed_sources()):
        try:
            hits = retrieval.diverse_search(collection, embedder, topic, k=5, per_file=2)
            st.caption("Local model: expect roughly 1-2 minutes. Text streams in below.")
            text = st.write_stream(llm.study_guide_stream(topic, hits))
            ss.guide = (topic, text)
        except llm.LLMError as err:
            st.error(str(err))
    elif ss.get("guide"):
        st.markdown(ss.guide[1])
    if ss.get("guide"):
        st.download_button(
            "Download as Markdown", ss.guide[1], f"{ss.guide[0][:40]}.md".replace(" ", "_")
        )

# ---------------------------------------------------------------- Progress
with tab_prog:
    o = store.overall()
    if not o["attempts"]:
        st.info("No scored quiz attempts yet.")
    else:
        st.metric("Overall accuracy", f"{o['accuracy']}%", f"{o['correct']} / {o['attempts']}")
        by_topic = store.accuracy_by("topic")
        st.subheader("Weakest topics")
        if by_topic:
            st.dataframe(by_topic, hide_index=True)
        else:
            st.caption("No topic data: add a syllabus before taking quizzes to get per-topic accuracy.")
        st.subheader("By document")
        st.dataframe(store.accuracy_by("source"), hide_index=True)
        wrong = store.wrong_questions()
        st.subheader(f"Review incorrect answers ({len(wrong)})")
        for w in wrong:
            with st.expander(f"{w['source']} p.{w['page']} Q{w['number']}"):
                st.write(w["stem"])
                st.write(f"You chose ({w['picked']}): {w['options'].get(w['picked'], '')}")
                st.write(f"Correct ({w['answer']}): {w['options'].get(w['answer'], '')}")
                if w["explanation"]:
                    st.caption(w["explanation"])
