#!/usr/bin/env python3
import os
import asyncio

# ── PATCHES: must run before importing Streamlit or torch ──

# 1. Disable Streamlit's file watcher (avoids torch.classes introspection errors)
os.environ["STREAMLIT_SERVER_ENABLE_FILE_WATCHER"] = "false"
# 2. Ensure there's always a running asyncio loop (fixes "no running event loop")
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# 3. Neutralize torch.classes __path__ to prevent missing-class errors
import torch
torch.classes.__path__ = []

# ── STANDARD IMPORTS ──

import requests
import uuid
import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit_lottie import st_lottie
from pinecone import Pinecone, ServerlessSpec
import chromadb
import tiktoken
from sentence_transformers import SentenceTransformer

# ── PAGE CONFIG ──

st.set_page_config(page_title="CampusGPT RAG Chat", page_icon="🎓", layout="wide")

# ── CUSTOM CSS ──

st.markdown(
    """
    <style>
      /* Chat bubbles */
      .stChatMessage {
        border-radius: 12px !important;
        padding: 8px !important;
        margin-bottom: 6px !important;
      }
      /* User bubbles */
      [data-testid="stChatMessage"][role="user"] .stChatMessage {
        background: linear-gradient(135deg,#ff9a9e,#fad0c4) !important;
      }
      /* Assistant bubbles */
      [data-testid="stChatMessage"][role="assistant"] .stChatMessage {
        background: linear-gradient(135deg,#89f7fe,#66a6ff) !important;
      }
      /* Chat input box */
      .stTextInput>div>div>input {
        border: 2px dashed #0072C6 !important;
        border-radius: 6px !important;
        padding: 8px !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── LOTTIE ANIMATION HEADER ──

def load_lottie(url: str):
    r = requests.get(url)
    return r.json() if r.status_code == 200 else {}

lottie_header = load_lottie("https://assets5.lottiefiles.com/packages/lf20_V9t630.json")
st_lottie(lottie_header, height=150, key="header")

st.title("🎓 Campus-GPT RAG powered Chatbot")
st.markdown(
    "Ask anything about Northern Kentucky University."
)

# ── SERVICE INIT ──

@st.cache_resource(show_spinner=False)
def init_services():
    load_dotenv()

    # Pinecone
    pc_key = os.getenv("PINECONE_API_KEY")
    pc_env = os.getenv("PINECONE_ENV")
    idx    = os.getenv("PINECONE_INDEX", "campus-gpt-index")
    if not pc_key or not pc_env:
        st.error("Missing PINECONE_API_KEY or PINECONE_ENV in .env")
        st.stop()
    pc = Pinecone(api_key=pc_key)
    if idx not in pc.list_indexes().names():
        pc.create_index(
            name=idx, dimension=384, metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=pc_env)
        )
    pine_index = pc.Index(idx)

    # ChromaDB
    chroma_client = chromadb.PersistentClient(path="chroma_store")
    collection    = chroma_client.get_or_create_collection(name="campus-gpt")

    # Embedder & tokenizer
    device    = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu"
    embedder  = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=device)
    tokenizer = tiktoken.get_encoding("cl100k_base")

    # DeepSeek
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    ds_url = os.getenv("DEEPSEEK_R1_URL")
    if not ds_key or not ds_url:
        st.error("Missing DEEPSEEK_API_KEY or DEEPSEEK_R1_URL in .env")
        st.stop()

    return pine_index, collection, embedder, tokenizer, ds_key, ds_url

pine_index, collection, EMBEDDER, TOKENIZER, DS_KEY, DS_URL = init_services()

# ── HELPER FUNCTIONS ──

def embed(text: str):
    return EMBEDDER.encode(text, normalize_embeddings=True).tolist()

def retrieve(query: str, top_k: int = 5):
    q_emb  = embed(query)
    resp   = pine_index.query(vector=q_emb, top_k=top_k, include_metadata=True)
    matches = getattr(resp, "matches", resp.get("matches", []))
    ids    = [m.id for m in matches]
    return collection.get(ids=ids).get("documents", []) if ids else []

def call_deepseek(prompt: str):
    headers = {
        "Authorization": f"Bearer {DS_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
              "role":    "system",
              "content": (
                  "Make sure you give a cool introduction before starting the conversation."
                  "You’re a funny, witty Gen-Z campus assistant called Vicor🎉. "
                  "Speak in slang, drop memes, use emojis, and keep it super conversational. "
                  "If you don’t know, just say  that  in the dankest way possible and ask for a followup to help with some other queries."
              )
            },
            {"role": "user", "content": prompt}
        ],
        "stream": False,
    }
    r = requests.post(DS_URL, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

# ── CHAT STATE ──

if "history" not in st.session_state:
    st.session_state.history = []

def chat_step():
    user_q = st.session_state.user_input.strip()
    if not user_q:
        return

    contexts = retrieve(user_q, top_k=5)
    if not contexts:
        st.session_state.history.append((user_q, "⚠️ IDK, fam—no relevant info found."))
        return

    prompt = "Answer using ONLY these NKU passages. If you’re clueless, say so.\n\n"
    for i, c in enumerate(contexts, 1):
        prompt += f"[Passage {i}]\n{c}\n\n"
    prompt += f"Question: {user_q}\nAnswer:"

    with st.spinner("💭 Thinking…"):
        answer = call_deepseek(prompt)

    st.session_state.history.append((user_q, answer))

# ── UI: chat_input & history ──

if st.chat_input("Hit me with your question…", key="user_input", on_submit=chat_step):
    pass

for user_msg, bot_msg in st.session_state.history:
    st.chat_message("user").write(user_msg)
    st.chat_message("assistant").write(bot_msg)

# ── Clear chat ──

if st.button("🗑️ Clear chat"):
    st.session_state.history = []
