"""Page styling, shared header and landing hero. Pure presentation; no app logic."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[2] / "assets"

_LOGO = (ASSETS / "logo.svg").read_text(encoding="utf-8")

_CSS = """
/* narrow screens: keep the nav links in a wrapped row instead of one per line */
@media (max-width: 640px) {
  .block-container { padding: 1rem 1rem 2rem; }
  .st-key-topnav [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .25rem .5rem; }
  .st-key-topnav [data-testid="stColumn"] { min-width: 0 !important; flex: 0 0 auto !important; width: auto !important; }
}

/* One blurred background for every page */
.stApp {
  background:
    radial-gradient(1100px 760px at 82% 38%, rgba(124,58,237,.55), transparent 65%),
    radial-gradient(800px 560px at 6% 105%, rgba(236,72,153,.22), transparent 60%),
    radial-gradient(900px 500px at 20% -10%, rgba(76,29,149,.35), transparent 60%),
    linear-gradient(135deg, #14101c 0%, #1a1130 55%, #0f0824 100%);
  background-attachment: fixed;
}
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stDecoration"], footer { display: none !important; }
.block-container { max-width: 100%; padding: 1.4rem 4rem 3rem; }
html, body, .stApp, button, input, textarea { font-family: 'Segoe UI', system-ui, -apple-system, Roboto, sans-serif; }

/* buttons & widgets */
.stButton > button, .stDownloadButton > button {
  border-radius: 999px; border: 1px solid rgba(192,132,252,.45);
  background: rgba(192,132,252,.12); color: #f4f1fa; padding: .45rem 1.3rem; font-weight: 500;
  transition: all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  background: #c084fc; color: #1a0b2e; border-color: #c084fc; transform: translateY(-1px);
}
.stButton > button:disabled { opacity: .4; }
[data-testid="stExpander"] { border-radius: 14px; border-color: rgba(255,255,255,.1); background: rgba(255,255,255,.03); }
[data-testid="stMetric"] {
  background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.1);
  border-radius: 16px; padding: .8rem 1rem;
}
[data-testid="stFileUploaderDropzone"], .stTextArea textarea, .stTextInput input,
[data-baseweb="select"] > div {
  background: rgba(255,255,255,.05) !important; border-color: rgba(255,255,255,.12) !important;
}

/* ---------- top navigation ---------- */
.ds-brand { display: flex; align-items: center; gap: 10px; font-size: 1.55rem; font-weight: 700; letter-spacing: -.02em; color: #f4f1fa; }
.ds-brand svg { width: 38px; height: 38px; }
.st-key-topnav a[data-testid="stPageLink-NavLink"] {
  justify-content: center; border-radius: 999px; padding: .4rem .8rem; background: transparent;
}
.st-key-topnav a[data-testid="stPageLink-NavLink"] p { color: #cfc6e8; font-size: .9rem; white-space: nowrap; }
.st-key-topnav a[data-testid="stPageLink-NavLink"]:hover p { color: #fff; }
.st-key-topnav a[data-testid="stPageLink-NavLink"][aria-current="page"] { background: rgba(192,132,252,.2); }
.st-key-topnav a[aria-current="page"] p { color: #fff; font-weight: 600; }
.st-key-nav_cta a[data-testid="stPageLink-NavLink"] {
  border: 1px solid rgba(180,160,255,.55); border-radius: 999px; justify-content: center; padding: .55rem 1.5rem;
}
.st-key-nav_cta a p { color: #fff; font-weight: 600; font-size: .9rem; }
.st-key-nav_cta a:hover { background: rgba(192,132,252,.25); }

/* ---------- page titles ---------- */
.ds-ptitle { margin: 1.6rem 0 1.2rem; }
.ds-ptitle h1 { font-size: 2.6rem; font-weight: 700; letter-spacing: -.03em; margin: 0; color: #fff; }
.ds-ptitle p { color: #b9b0d6; margin: .3rem 0 0; font-size: 1.02rem; }

/* ---------- hero (fills the window, no card) ---------- */
.st-key-hero { min-height: calc(100vh - 150px); display: flex; flex-direction: column; justify-content: center; }
.ds-copy h1 { font-size: 5.2rem; line-height: 1.02; font-weight: 700; letter-spacing: -.035em; margin: 0 0 26px; color: #fff; }
.ds-grad {
  background: linear-gradient(90deg, #ffffff 0%, #f4e6ff 45%, #f9a8d4 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.ds-copy p { max-width: 520px; color: #cfc6e8; font-size: 1.12rem; line-height: 1.65; margin: 0 0 30px; }
.st-key-hero_cta a[data-testid="stPageLink-NavLink"] {
  background: #c996fb; border-radius: 999px; padding: .85rem 2.2rem; width: fit-content; justify-content: center;
  box-shadow: 0 10px 30px rgba(192,132,252,.35);
}
.st-key-hero_cta a p { color: #1b0d33; font-weight: 700; font-size: 1rem; white-space: nowrap; }
.st-key-hero_cta a:hover { background: #d8b4fe; }
.ds-note { font-size: .85rem; color: #b3a8d4; margin-top: 14px; }
.ds-stack { display: flex; gap: 34px; margin-top: 70px; color: #9d92c2; font-weight: 600; font-size: 1.05rem; }

/* ---------- phone mock ---------- */
.ds-stage { position: relative; height: 680px; perspective: 1600px; }
.ds-float { position: absolute; inset: 0; animation: ds-float 7s ease-in-out infinite; }
@keyframes ds-float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
.ds-phone {
  position: absolute; left: calc(50% - 190px); top: 30px; width: 360px; height: 600px;
  transform-style: preserve-3d; transform: scale(1.08) rotateX(16deg) rotateY(-26deg) rotateZ(7deg);
}
.ds-glass {
  background: linear-gradient(160deg, rgba(255,255,255,.22), rgba(255,255,255,.06));
  border: 1px solid rgba(255,255,255,.25); backdrop-filter: blur(10px);
  border-radius: 34px; box-shadow: 0 30px 60px rgba(8,2,30,.55);
}
.ds-back { position: absolute; inset: 0; background: linear-gradient(160deg, rgba(190,170,255,.28), rgba(70,40,140,.35)); }
.ds-top { position: absolute; top: 18px; left: 0; right: 0; text-align: center; font-weight: 600; font-size: .95rem; color: #fff; }
.ds-top i { position: absolute; left: 26px; font-style: normal; opacity: .85; }
.ds-top b { position: absolute; right: 26px; letter-spacing: 2px; }
.ds-layer { position: absolute; left: 14px; right: 14px; border-radius: 26px; background: rgba(150,130,200,.35); border: 1px solid rgba(255,255,255,.2); height: 150px; }
.ds-l1 { top: 112px; transform: translateZ(6px); }
.ds-l2 { top: 100px; transform: translateZ(14px); left: 20px; right: 20px; }
.ds-profile {
  position: absolute; top: 62px; left: 18px; right: 18px; height: 168px; border-radius: 28px;
  background: linear-gradient(150deg, rgba(210,195,245,.55), rgba(120,95,190,.55));
  border: 1px solid rgba(255,255,255,.3); transform: translateZ(26px); padding: 18px 20px;
}
.ds-profile h3 { margin: 34px 0 4px; font-size: 1.3rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.ds-pill { background: #bbf7d0; color: #14532d; font-size: .6rem; font-weight: 700; border-radius: 999px; padding: 2px 8px; }
.ds-profile small { display: block; color: #e9ddff; font-size: .72rem; white-space: nowrap; }
.ds-ico {
  position: absolute; top: -14px; right: -10px; width: 62px; height: 62px; border-radius: 20px;
  background: #fcd34d; display: grid; place-items: center; box-shadow: 0 10px 24px rgba(0,0,0,.3);
}
.ds-ico svg { width: 30px; height: 30px; }
.ds-circle {
  position: absolute; right: -14px; top: 78px; width: 46px; height: 46px; border-radius: 50%;
  border: 1.5px solid rgba(255,255,255,.7); display: grid; place-items: center; background: rgba(60,30,110,.5);
}
.ds-black {
  position: absolute; left: 14px; right: 40px; bottom: 14px; height: 40px; border-radius: 999px;
  background: #0e0b16; color: #fff; font-weight: 600; font-size: .85rem; display: grid; place-items: center;
}
.ds-stats {
  position: absolute; top: 258px; left: 22px; right: 22px; display: flex; justify-content: space-between;
  font-size: .78rem; color: #cbbfee; font-weight: 600; transform: translateZ(20px);
}
.ds-stats span:first-child { color: #fff; }
.ds-green {
  position: absolute; top: 292px; left: 14px; right: 14px; height: 190px; border-radius: 28px;
  background: #c8f5c0; color: #12301a; padding: 18px 20px; transform: translateZ(34px);
  box-shadow: 0 24px 50px rgba(0,0,0,.4);
}
.ds-green .tag { position: absolute; top: 16px; right: 20px; font-size: .72rem; font-weight: 600; color: #234b2c; }
.ds-green .chk { font-size: 1.2rem; font-weight: 800; }
.ds-green h4 { position: absolute; left: 20px; bottom: 58px; margin: 0; font-size: 1.3rem; font-weight: 700; color: #12301a; }
.ds-green .sub { position: absolute; left: 20px; bottom: 36px; font-size: .74rem; color: #2f5b38; }
.ds-green .sub2 { position: absolute; left: 20px; bottom: 18px; font-size: .7rem; color: #3f6f48; }
.ds-green .qz {
  position: absolute; right: 18px; bottom: 22px; width: 54px; height: 54px; border-radius: 18px;
  background: #0e0b16; display: grid; place-items: center; color: #c4b5fd; font-weight: 700; font-size: .8rem;
}
.ds-hist {
  position: absolute; top: 468px; left: 18px; right: 6px; height: 110px; border-radius: 26px;
  background: #100c1c; color: #fff; padding: 16px 20px; transform: translateZ(30px); font-size: .8rem;
}
.ds-hist b { display: block; font-size: 1.05rem; margin-bottom: 4px; }
.ds-hist span { color: #b8aedb; }
.ds-peek {
  position: absolute; right: -30px; top: 318px; width: 120px; height: 150px; border-radius: 28px;
  background: linear-gradient(160deg, #fbd9c0, #c68ba3); color: #3a1630; padding: 16px; font-weight: 700;
  transform: translateZ(60px) rotateY(-10deg); box-shadow: 0 24px 50px rgba(0,0,0,.4); font-size: .85rem;
}
.ds-peek small { display: block; font-weight: 600; opacity: .75; margin-top: 4px; }
.ds-foot { text-align: right; font-size: .72rem; color: #8f84b5; margin-top: -10px; }

@media (max-width: 980px) {
  .ds-stage, .ds-foot { display: none; }
  .ds-copy h1 { font-size: 3rem; }
  .block-container { padding: 1rem 1.2rem 2rem; }
}
"""

_BRAND = f'<div class="ds-brand">{_LOGO}<span>Docusense.</span></div>'

_COPY = """
<div class="ds-copy">
<h1><span class="ds-grad">Docusense</span><br>Your SuperAI</h1>
<p>Docusense is a syllabus-driven study companion. It reads your PDFs, answers with
page-level citations, shows which syllabus topics your notes actually cover, and turns
your question banks into scored practice.</p>
</div>
"""

_AFTER_CTA = """
<div class="ds-copy"><div class="ds-note">Runs locally with Ollama. Your files stay on your machine.</div>
<div class="ds-stack"><span>Ollama</span><span>ChromaDB</span><span>PyMuPDF</span><span>Streamlit</span></div></div>
"""

_PHONE = """
<div class="ds-stage"><div class="ds-float"><div class="ds-phone">
<div class="ds-glass ds-back"></div>
<div class="ds-top"><i>&lsaquo;</i>Syllabus coverage<b>&middot;&middot;&middot;</b></div>
<div class="ds-layer ds-l1"></div><div class="ds-layer ds-l2"></div>
<div class="ds-profile">
<div class="ds-ico"><svg viewBox="0 0 24 24" fill="none" stroke="#1b1b1b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h8l4 4v14H6z"/><path d="M9 12h6M9 16h4"/></svg></div>
<div class="ds-circle"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg></div>
<h3>Data Structures <span class="ds-pill">1/5 topics</span></h3>
<small>ds_notes.pdf &middot; ds_slides.pdf &middot; ds_quiz.pdf</small>
<div class="ds-black">Add PDFs</div>
</div>
<div class="ds-stats"><span>3 documents</span><span>4 MCQs</span><span>5 topics</span></div>
<div class="ds-green">
<span class="chk">&#10003;</span><span class="tag">3 sources</span>
<h4>Binary Trees</h4><div class="sub">Covered &middot; ds_notes.pdf p.1</div>
<div class="sub2">ds_slides.pdf p.1 &middot; ds_quiz.pdf p.1</div>
<div class="qz">Quiz</div>
</div>
<div class="ds-hist"><b>Recent questions</b><span>Which traversal of a BST gives sorted order?</span></div>
<div class="ds-peek">Quiz score<small>3 / 4 correct</small></div>
</div></div></div>
<div class="ds-foot">Illustration uses the bundled sample PDFs</div>
"""


def _html(block: str) -> str:
    # one line per tag: blank lines/indents would trip the markdown parser
    return " ".join(line.strip() for line in block.splitlines())


def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def header(pages) -> None:
    """Brand + page links + CTA. Rendered once per run above the active page."""
    with st.container(key="topnav"):
        brand, nav, cta = st.columns([2.2, 8, 1.8], vertical_alignment="center")
        brand.markdown(_BRAND, unsafe_allow_html=True)
        with nav:
            widths = [len(p.title) + 4 for p in pages]  # roughly even visual gaps
            for col, page in zip(st.columns(widths, gap="small"), pages):
                col.page_link(page, label=page.title)
        with cta.container(key="nav_cta"):
            st.page_link(pages[1], label="Get started")


def page_title(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="ds-ptitle"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def hero(documents_page: str) -> None:
    """Full-window landing hero. `documents_page` is the CTA's target page path."""
    with st.container(key="hero"):
        left, right = st.columns([1.05, 1], vertical_alignment="center", gap="large")
        with left:
            st.markdown(_html(_COPY), unsafe_allow_html=True)
            with st.container(key="hero_cta"):
                st.page_link(documents_page, label="Upload your PDFs")
            st.markdown(_html(_AFTER_CTA), unsafe_allow_html=True)
        with right:
            st.markdown(_html(_PHONE), unsafe_allow_html=True)
