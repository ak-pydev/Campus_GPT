#!/usr/bin/env python3
import os
import json
import uuid
import argparse
from pathlib import Path
from dotenv import load_dotenv
from tqdm.auto import tqdm
import chromadb
from pinecone import Pinecone, ServerlessSpec

# ─── CLI & Config ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Ingest embeddings into Pinecone & ChromaDB"
)
parser.add_argument(
    "input_file",
    nargs="?",
    default="processed/pinecone_input.jsonl",
    help="Path to your JSONL file (default: processed/pinecone_input.jsonl)"
)
args = parser.parse_args()
INPUT_FILE = Path(args.input_file)
if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Could not find input file: {INPUT_FILE}")  # Path.exists() check :contentReference[oaicite:5]{index=5}

# Load environment
load_dotenv()
API_KEY = os.getenv("PINECONE_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing PINECONE_API_KEY in environment")  # dotenv usage :contentReference[oaicite:6]{index=6}

# ─── Pinecone Setup ────────────────────────────────────────────────────────────
pc = Pinecone(api_key=API_KEY)
index_name = "campus-gpt-index"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=384,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )  # Pinecone index creation :contentReference[oaicite:7]{index=7}
index = pc.Index(index_name)

# ─── ChromaDB Setup ────────────────────────────────────────────────────────────
chroma_client = chromadb.PersistentClient(path="chroma_store")
collection = chroma_client.get_or_create_collection(name="campus-gpt")

# ─── Batch Helpers ─────────────────────────────────────────────────────────────
batch_size = 100
pinecone_vectors = []
chroma_ids = []
chroma_texts = []
chroma_metadatas = []

def flush_batch():
    """Flush both Pinecone and ChromaDB in one go."""
    if not pinecone_vectors:
        return
    index.upsert(vectors=pinecone_vectors)
    collection.add(
        documents=chroma_texts,
        metadatas=chroma_metadatas,
        ids=chroma_ids
    )
    pinecone_vectors.clear()
    chroma_ids.clear()
    chroma_texts.clear()
    chroma_metadatas.clear()

# ─── Main Loop ─────────────────────────────────────────────────────────────────
print(f"📤 Uploading from {INPUT_FILE}")
with open(INPUT_FILE, encoding="utf-8") as f:
    for idx, line in enumerate(tqdm(f, desc="Uploading")):
        doc = json.loads(line)
        meta = doc.get("metadata", {})
        slug = meta.get("slug") or str(uuid.uuid4())  # uuid fallback :contentReference[oaicite:8]{index=8}
        title = meta.get("title") or ""              # avoid null title :contentReference[oaicite:9]{index=9}
        doc_id = f"{slug}-{idx}"

        # Prepare Pinecone payload
        pinecone_vectors.append({
            "id":       doc_id,
            "values":   doc["embedding"],
            "metadata": {"slug": slug, "title": title}
        })

        # Prepare ChromaDB payload
        chroma_ids.append(doc_id)
        chroma_texts.append(doc["text"])
        chroma_metadatas.append(meta)

        if len(pinecone_vectors) >= batch_size:
            flush_batch()

# Final flush
flush_batch()
print("✅ Uploaded embeddings to Pinecone and documents to ChromaDB!")
