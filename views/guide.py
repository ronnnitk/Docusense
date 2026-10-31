import streamlit as st

from docusense import llm, retrieval, shared, ui

ui.page_title("Study guide", "Cross-document revision notes with citations.")

ss = st.session_state

opts = shared.topics()
topic = st.selectbox("Pick a syllabus topic", opts) if opts else None
custom = st.text_input("...or type any topic", value="")
topic = custom.strip() or topic
fresh = st.checkbox("Fresh guide (ignore the saved one for this topic)")

if st.button("Generate study guide", disabled=not topic or not shared.indexed_sources()):
    try:
        hits = retrieval.diverse_search(
            shared.get_collection(), shared.embedder(), topic, k=5, per_file=2
        )
        st.caption("Local model: expect roughly 1 minute. Text streams in below.")
        text = st.write_stream(llm.study_guide_stream(topic, hits, fresh=fresh))
        ss.guide = (topic, text)
    except llm.LLMError as err:
        st.error(str(err))
elif ss.get("guide"):
    st.markdown(ss.guide[1])
if ss.get("guide"):
    st.download_button(
        "Download as Markdown", ss.guide[1], f"{ss.guide[0][:40]}.md".replace(" ", "_")
    )
