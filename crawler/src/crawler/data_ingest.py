#!/usr/bin/env python3
import os
import json
import asyncio
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

DATA_FILE    = Path("processed/chromadb_input.jsonl")
CHROMA_PATH  = "chroma_store"
COLLECTION   = "campus_gpt"
BATCH_SIZE   = 100
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def init_chroma(path: str, collection_name: str):
    client = chromadb.PersistentClient(path=path)
    collection = client.get_or_create_collection(name=collection_name)
    return collection

async def ingest(collection, file_path: Path, batch_size: int):
    model = SentenceTransformer(EMBEDDING_MODEL)
    ids, docs, metas = [], [], []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            _id   = record.get("id") or str(record.get("chunk_id", ""))
            text  = record.get("text", "")
            meta  = record.get("metadata", {})

            if not _id or not text:
                continue

            ids.append(_id)
            docs.append(text)
            metas.append(meta)

            if len(ids) >= batch_size:
                embs = model.encode(docs).tolist()
                collection.add(
                    ids=ids,
                    documents=docs,
                    embeddings=embs,
                    metadatas=metas
                )
                ids, docs, metas = [], [], []

        if ids:
            embs = model.encode(docs).tolist()
            collection.add(
                ids=ids,
                documents=docs,
                embeddings=embs,
                metadatas=metas
            )

async def query(collection, model, query_text: str, top_k: int = 5):
    q_emb = model.encode([query_text]).tolist()
    results = collection.query(
        query_embeddings=q_emb,
        n_results=top_k
    )
    hits = list(zip(results["ids"][0], results["documents"][0], results["metadatas"][0]))
    print(f"\nTop {top_k} results for: '{query_text}'\n")
    for idx, (doc_id, doc_text, meta) in enumerate(hits, start=1):
        print(f"{idx}. ID: {doc_id}")
        print(f"   Text: {doc_text[:200]}{'…' if len(doc_text)>200 else ''}")
        print(f"   Metadata: {meta}\n")

def main():
    collection = init_chroma(CHROMA_PATH, COLLECTION)
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Ingesting data into ChromaDB…")
    asyncio.run(ingest(collection, DATA_FILE, BATCH_SIZE))
    print("Ingestion complete.")

    while True:
        query_text = input("\nEnter a query (or 'quit' to exit): ").strip()
        if not query_text or query_text.lower() == "quit":
            break
        asyncio.run(query(collection, model, query_text))

if __name__ == "__main__":
    main()
