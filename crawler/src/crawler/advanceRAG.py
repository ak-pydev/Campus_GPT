# advanceRAG.py

import os
import asyncio
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit_lottie import st_lottie
from streamlit.components.v1 import html

import requests
from typing import List

from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import chromadb
from chromadb.config import Settings
import tiktoken

# ─── PAGE CONFIG & ASSETS ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎓 Advanced RAG Explorer",
    page_icon="🎓",
    layout="wide",
)

# Load a Lottie animation for the header
def load_lottie(url: str):
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    return {}

lottie_header = load_lottie("https://assets6.lottiefiles.com/packages/lf20_u4yrau.json")
st_lottie(lottie_header, height=200, key="header")

st.title("Advanced RAG Explorer")
st.markdown(
    """
    A next-gen Retrieval-Augmented Generation interface.  
    Upload documents or point to your Pinecone/ChromaDB index,  
    tweak retrieval & generation settings, and get instant answers!
    """,
    unsafe_allow_html=True,
)

# ─── SIDEBAR CONFIG ────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Configuration")
with st.sidebar.form("config_form"):
    use_pinecone = st.checkbox("Enable Pinecone", value=True)
    use_chroma = st.checkbox("Enable ChromaDB", value=True)
    api_key = st.text_input("Pinecone API Key", type="password")
    pc_env = st.text_input("Pinecone Environment", value="us-east-1")
    chroma_dir = st.text_input("Chroma Dir", value="chroma_store")
    submitted = st.form_submit_button("Save")
    if submitted:
        os.environ["PINECONE_API_KEY"] = api_key
        os.environ["PINECONE_ENV"] = pc_env
        os.environ["CHROMA_PERSIST_DIR"] = chroma_dir
        st.experimental_rerun()

# ─── INITIALIZE SERVICES ───────────────────────────────────────────────────────
@st.cache_resource
def init_services():
    load_dotenv()
    pine_index = None
    if use_pinecone:
        pc_key = os.getenv("PINECONE_API_KEY")
        pc_env = os.getenv("PINECONE_ENV")
        if not pc_key or not pc_env:
            st.error("Pinecone credentials missing!")
            st.stop()
        pc = Pinecone(api_key=pc_key)
        idx = os.getenv("PINECONE_INDEX", "campus-gpt-index")
        if idx not in pc.list_indexes().names():
            pc.create_index(
                name=idx, dimension=384, metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=pc_env)
            )
        pine_index = pc.Index(idx)

    chroma_client = None
    chroma_col = None
    if use_chroma:
        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "chroma_store")
        chroma_client = chromadb.PersistentClient(
            path=chroma_dir,
            settings=Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=chroma_dir
            )
        )
        chroma_col = chroma_client.get_or_create_collection("campus-gpt")

    device = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu"
    embedder = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=device)
    tokenizer = tiktoken.get_encoding("cl100k_base")

    return pine_index, chroma_col, embedder, tokenizer

pine_index, chroma_col, EMBEDDER, TOKENIZER = init_services()

# ─── RAG HELPERS ───────────────────────────────────────────────────────────────
def embed(text: str):
    return EMBEDDER.encode(text, normalize_embeddings=True).tolist()

def retrieve_pinecone(query: str, top_k: int) -> List[str]:
    q_emb = embed(query)
    resp = pine_index.query(vector=q_emb, top_k=top_k, include_metadata=True)
    matches = getattr(resp, "matches", resp.get("matches", []))
    return [m.metadata.get("text", "") for m in matches]

def retrieve_chroma(query: str, top_k: int) -> List[str]:
    q_emb = embed(query)
    results = chroma_col.query(query_embeddings=[q_emb], n_results=top_k)
    return results["documents"][0]

# ─── UI: Query Input ──────────────────────────────────────────────────────────
st.subheader("🔎 Ask a Question")
user_query = st.text_input("Your question:", placeholder="e.g. What are NKU admission requirements?")
top_k = st.slider("Number of context passages", 3, 10, 5)

if st.button("Run RAG"):
    if not user_query:
        st.warning("Enter a question first!")
    else:
        with st.spinner("Retrieving context…"):
            contexts = []
            if use_pinecone:
                contexts += retrieve_pinecone(user_query, top_k)
            if use_chroma:
                contexts += retrieve_chroma(user_query, top_k)
        st.success("Context retrieved!")

        st.markdown("**Context Passages**")
        for i, ctx in enumerate(contexts, 1):
            st.markdown(f"> **Passage {i}:** {ctx[:500]}...")

        st.markdown("---")
        st.subheader("📝 Generated Answer")
        prompt = "\n\n".join(contexts) + f"\n\nQuestion: {user_query}\nAnswer:"
        # Here you’d call your LLM (OpenAI, DeepSeek, etc.)
        fake_answer = "This is where the LLM’s response will appear."
        st.write(fake_answer)

# ─── FUN ANIMATIONS & FOOTER ──────────────────────────────────────────────────
if st.button("🎉 Celebrate"):
    st.balloons()

st.markdown(
    """
    <style>
      footer {visibility: hidden;}
      .stApp {background: linear-gradient(135deg, #f0f9ff, #cbebff);}
    </style>
    """,
    unsafe_allow_html=True,
)
