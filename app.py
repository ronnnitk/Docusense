
import re
import random
import time
import streamlit as st
import pymupdf
import chromadb
import ollama
from sentence_transformers import SentenceTransformer

st.set_page_config(page_title="DocuSense AI", page_icon="📚")
st.title("📚 DocuSense AI")
st.write("Upload your study PDFs and ask questions from their content.")

@st.cache_resource
def load_model():
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

@st.cache_resource
def load_database():
    client = chromadb.PersistentClient(path="./chroma_db")
    return client

embedder = load_model()
client = load_database()


if "indexed" not in st.session_state:
    try:
        collection = client.get_collection("docusense_documents")
        st.session_state["indexed"] = collection.count() > 0
    except Exception:
        st.session_state["indexed"] = False


def extract_chunks(uploaded_files):
    chunks = []
    metadatas = []
    ids = []

    for file in uploaded_files:
        pdf = pymupdf.open(stream=file.getvalue(), filetype="pdf")

        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text().strip()
            if not text:
                continue

            chunk_size = 1000
            overlap = 150
            start = 0
            chunk_number = 0

            while start < len(text):
                chunk = text[start:start + chunk_size].strip()

                if chunk:
                    chunks.append(chunk)
                    metadatas.append({
                        "source": file.name,
                        "page": page_number
                    })
                    ids.append(
                        f"{file.name}_{page_number}_{chunk_number}"
                    )

                start += chunk_size - overlap
                chunk_number += 1

        pdf.close()

    return chunks, metadatas, ids


def extract_mcqs(uploaded_files):
    mcqs = []

    for file in uploaded_files:
        pdf = pymupdf.open(
            stream=file.getvalue(),
            filetype="pdf"
        )

        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")

            # Find each question starting with Q followed by a number.
            matches = list(re.finditer(
                r"(?im)^\s*Q\s*\d+\s*[.)]\s*",
                text
            ))

            for i, match in enumerate(matches):
                start = match.start()
                end = (
                    matches[i + 1].start()
                    if i + 1 < len(matches)
                    else len(text)
                )

                question_text = text[start:end].strip()

                # Keep only entries that look like MCQs.
                options = re.findall(
                    r"(?im)^\s*\([A-D]\)\s*",
                    question_text
                )

                if len(options) >= 2:
                    mcqs.append({
                        "source": file.name,
                        "page": page_number,
                        "question": question_text
                    })

        pdf.close()

    return mcqs

uploaded_files = st.file_uploader(
    "Upload your PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files and st.button("Preview extracted MCQs"):
    mcqs = extract_mcqs(uploaded_files)

    st.write(f"Found {len(mcqs)} MCQs")

    for mcq in mcqs[:5]:
        with st.expander(
            f"{mcq['source']} — Page {mcq['page']}"
        ):
            st.text(mcq["question"])

if uploaded_files and st.button("Start MCQ Practice"):
    mcqs = extract_mcqs(uploaded_files)

    if mcqs:
        st.session_state.practice_mcqs = mcqs
        st.session_state.practice_order = random.sample(
            range(len(mcqs)), len(mcqs)
        )
        st.session_state.practice_index = 0
    else:
        st.warning("No MCQs found in the uploaded PDFs.")

if "practice_mcqs" in st.session_state:
    mcqs = st.session_state.practice_mcqs
    order = st.session_state.practice_order
    index = st.session_state.practice_index

    if index < len(order):
        mcq = mcqs[order[index]]

        st.subheader(
            f"Practice Question {index + 1} of {len(order)}"
        )
        st.caption(f"Source: {mcq['source']} | Page: {mcq['page']}")
        st.text(mcq["question"])

        if st.button("Next Question"):
            st.session_state.practice_index += 1
            st.rerun()
    else:
        st.success("You completed all the MCQs!")

if st.button("Process PDFs"):
    if not uploaded_files:
        st.warning("Please upload at least one PDF.")
    else:
        with st.spinner("Reading PDFs and creating embeddings..."):
            chunks, metadatas, ids = extract_chunks(uploaded_files)

            if not chunks:
                st.error(
                    "No selectable text found. Scanned PDFs need OCR."
                )
            else:
                try:
                    client.delete_collection("docusense_documents")
                except Exception:
                    pass

                collection = client.create_collection(
                    name="docusense_documents",
                    metadata={"hnsw:space": "cosine"}
                )

                embeddings = embedder.encode(
                    chunks,
                    normalize_embeddings=True
                ).tolist()

                collection.add(
                    documents=chunks,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )

                st.session_state["indexed"] = True
                st.success(f"Processed {len(chunks)} text chunks!")

def answer_question(question):
    collection = client.get_collection("docusense_documents")
    t0=time.perf_counter()
    query_embedding = embedder.encode(
        [question],
        normalize_embeddings=True
    ).tolist()

    t1=time.perf_counter()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=4
    )
    t2=time.perf_counter()

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_parts = []
    for i, (document, metadata) in enumerate(
        zip(documents, metadatas), start=1
    ):
        context_parts.append(
            f"[Source {i}: {metadata['source']}, "
            f"page {metadata['page']}]\n{document}"
        )

    context = "\n\n".join(context_parts)

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are DocuSense AI, an academic study assistant. "
        "Use only the supplied PDF context. "
        "Answer directly and concisely. "
        "For MCQs, reproduce the question and options only if available "
        "in the context, then give the correct option and a brief reason. "
        "Do not invent missing options or facts. "
        "Cite supporting material using [Source 1], [Source 2], etc. "
        "If the context is insufficient, say so."
                )
            },
            {
                "role": "user",
                "content": (
                    f"PDF CONTEXT:\n{context}\n\n"
                    f"QUESTION:\n{question}"
                )
            }
        ],
        options={
            "temperature": 0.1,
            "num_predict": 200
            }
    )
    t3=time.perf_counter()

    print(f"Query embedding : {t1-t0:.2f}s")
    print(f"Vector search : {t2-t1:.2f}s")
    print(f"LLM generation : {t3-t2:.2f}s")

    return response["message"]["content"], metadatas, results

if st.session_state.get("indexed", False):
    st.subheader("Ask a question")
    question = st.text_input(
        "What would you like to understand from your PDFs?"
    )

    if st.button("Ask DocuSense"):
        if question.strip():
            with st.spinner("Finding relevant content and generating answer..."):
                try:
                    answer, metadatas, results = answer_question(question)
                    st.markdown("### Answer")
                    st.write(answer)

                    st.markdown("### Retrieved sources")

                    documents = results["documents"][0]

                    for i, (metadata, document) in enumerate(
                        zip(metadatas, documents), start=1
                    ):
                        with st.expander(
                            f"[Source {i}] {metadata['source']} — Page {metadata['page']}"
                        ):
                            st.write(document)
                except Exception as error:
                    st.error(f"Something went wrong: {error}")
else:
    st.info("Upload PDFs and click 'Process PDFs' to get started.")
