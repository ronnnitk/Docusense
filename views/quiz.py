import streamlit as st
from streamlit_lottie import st_lottie

from docusense import llm, qgen, retrieval, shared, syllabus, ui
from docusense.quiz import QuizSession

ui.page_title("Quiz", "Practice your question bank. Scored only when a question has a known answer.")

store = shared.get_store()
ss = st.session_state
correct_animation = shared.animation("Congratulations.json")
incorrect_animation = shared.animation("Incorrect.json")

quiz: QuizSession | None = ss.get("quiz")

if quiz is None and shared.indexed_sources():
    with st.expander("Generate practice questions from my notes (AI)"):
        st.caption(
            "Each question is written from one excerpt of your documents. It is kept only if its "
            "supporting quote really appears on that page and no wrong option is also supported "
            "by the text. Many drafts get rejected, and it takes roughly 20-40 s per question."
        )
        opts = shared.topics()
        topic = st.selectbox("Syllabus topic", opts) if opts else None
        custom = st.text_input("...or type any topic", key="gen_topic")
        topic = custom.strip() or topic
        count = st.slider("How many chunks to try", 1, 5, 3)
        if st.button("Generate questions", disabled=not topic):
            try:
                hits = retrieval.diverse_search(
                    shared.get_collection(), shared.embedder(), topic, k=count, per_file=2
                )
                made, notes = [], []
                with st.status("Generating...", expanded=True) as status:
                    for i, hit in enumerate(hits, start=1):
                        st.write(f"{i}/{len(hits)}: {hit.source} p.{hit.page}")
                        mcq, why = qgen.generate_one(hit)
                        if mcq:
                            made.append(mcq)
                        else:
                            notes.append(f"{hit.source} p.{hit.page}: rejected ({why})")
                    status.update(label=f"Kept {len(made)} of {len(hits)}", state="complete")
                if made:
                    store.add_questions(made)
                    st.success(f"Added {len(made)} question(s) to your bank.")
                for note in notes:
                    st.caption(note)
            except llm.LLMError as err:
                st.error(str(err))

bank = store.load_questions()
if not bank:
    st.info("No MCQs yet. Process PDFs that contain multiple-choice questions (Documents page).")
    st.stop()

if quiz is None:
    files_with_q = sorted({q.source for q in bank})
    picked = st.multiselect("Practice from", files_with_q, default=files_with_q)
    only_key = st.checkbox("Only questions with an answer (scored)", value=True)
    n_gen = sum(q.generated for q in bank)
    include_gen = st.checkbox(f"Include AI-generated questions ({n_gen})", value=bool(n_gen), disabled=not n_gen)
    pool = [
        q for q in bank
        if q.source in picked and (q.answer or not only_key) and (include_gen or not q.generated)
    ]
    st.write(f"{len(pool)} questions available.")
    if st.button("Start quiz", disabled=not pool):
        ss.quiz = QuizSession.new(pool)
        ss.pop("provisional", None)
        st.rerun()
    st.stop()

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
    st.stop()

resp = quiz.response_for_current()
s = quiz.summary()
st.subheader(f"Question {quiz.pos + 1} of {quiz.total}")
label = "AI-generated" if q.generated else f"Q{q.number}"
st.caption(f"{q.source} · page {q.page} · {label} · score so far {s['correct']} / {s['scored']}")
st.write(q.stem)
choice = st.radio(
    "Options",
    list(q.options),
    index=list(q.options).index(resp.selected) if resp else None,
    format_func=lambda k: f"({k}) {q.options[k]}",
    key=f"sel_{q.id}",
    disabled=resp is not None,
    label_visibility="collapsed",
)

if resp is None:
    if st.button("Check answer", disabled=choice is None):
        quiz.submit(choice)
        store.record_attempt(q, choice, syllabus.assign_topic(
            q.stem + " " + " ".join(q.options.values()), shared.topics()))
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
        st_lottie(
            correct_animation,
            speed=2,
            reverse=False,
            loop=False,
            quality="high",
            height=180,
            key=f"Correct_animation_{q.id}",
        )
        st.success(f"Correct! ({resp.correct})")
    else:
        st_lottie(
            incorrect_animation,
            speed=10,
            reverse=False,
            loop=False,
            quality="high",
            height=180,
            key=f"Incorrect_animation_{q.id}",
        )
        st.error(f"Wrong. You chose ({resp.selected}); correct is ({resp.correct}).")
    if q.explanation:
        st.caption(("Explanation: " if q.generated else "Explanation (from the PDF): ") + q.explanation)
    if q.generated:
        st.caption(
            "AI-generated. The answer is backed by the quote above, but AI questions can "
            "still be imperfect - check the source page if unsure."
        )

    last = quiz.pos + 1 == quiz.total
    if st.button("Finish" if last else "Next question"):
        quiz.next()
        st.rerun()

if st.button("Quit quiz"):
    del ss["quiz"]
    st.rerun()
