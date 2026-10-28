import streamlit as st

from docusense import shared, ui

ui.page_title("Progress", "Accuracy by topic and document, and the questions to revisit.")

store = shared.get_store()

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
