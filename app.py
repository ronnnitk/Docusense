"""Docusense entrypoint: shared header + page navigation. Pages live in views/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:  # Streamlit Cloud's system SQLite can be too old for ChromaDB
    import pysqlite3  # noqa: F401

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import os  # noqa: E402

import streamlit as st  # noqa: E402

from docusense import shared, ui  # noqa: E402

st.set_page_config(
    page_title="Docusense",
    page_icon=str(Path(__file__).parent / "assets" / "logo.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)
try:  # hosted: the key lives in Streamlit Cloud "Secrets", never in the repo
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass  # no secrets file locally: use Ollama
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
