"""Docusense entrypoint: shared header + page navigation. Pages live in views/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st  # noqa: E402

from docusense import shared, ui  # noqa: E402

st.set_page_config(
    page_title="Docusense",
    page_icon=str(Path(__file__).parent / "assets" / "logo.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)
ui.inject_css()
shared.init()

pages = [
    st.Page("views/home.py", title="Home", default=True),
    st.Page("views/documents.py", title="Documents", url_path="documents"),
    st.Page("views/ask.py", title="Ask", url_path="ask"),
    st.Page("views/quiz.py", title="Quiz", url_path="quiz"),
    st.Page("views/coverage.py", title="Syllabus", url_path="syllabus"),
    st.Page("views/guide.py", title="Study guide", url_path="guide"),
    st.Page("views/progress.py", title="Progress", url_path="progress"),
]
current = st.navigation(pages, position="hidden")
ui.header(pages)
current.run()
