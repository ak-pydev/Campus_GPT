#!/usr/bin/env python3
import os
import re
import json
import uuid
import asyncio
import logging
from pathlib import Path
from typing import List, Dict

import aiofiles
import backoff
import chromadb
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException
from tqdm.asyncio import tqdm_asyncio

# ─── CONFIG ───────────────────────────────────────────────────────────
load_dotenv()  # only for PINECONE_API_KEY and PINECONE_ENVIRONMENT
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENV     = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
INDEX_NAME       = os.getenv("PINECONE_INDEX", "campus-gpt-index")
FILE_PATH        = Path("processed/pinecone_input.jsonl")
BATCH_SIZE       = int(os.getenv("UPLOAD_BATCH_SIZE", "100"))
CHROMA_PATH      = "chroma_store"  

# ─── LOGGING ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── TEXT CLEANING ──────────────────────────────────────────────────────
def clean_text(raw: str) -> str:
    # remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', raw)
    # strip non-ASCII
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

# ─── ENV VALIDATION ─────────────────────────────────────────────────────
if not PINECONE_API_KEY:
    logger.error("PINECONE_API_KEY is not set! Exiting.")
    raise SystemExit(1)

# ─── INIT PINECONE ─────────────────────────────────────────────────────
logger.info("Initializing Pinecone client…")
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)

# Infer embedding dim from first record
if not FILE_PATH.exists():
    logger.error(f"Input file not found: {FILE_PATH}")
    raise SystemExit(1)
with open(FILE_PATH, "r", encoding="utf-8") as f:
    first = json.loads(f.readline())
    dim = len(first.get("embedding", []))
    if dim == 0:
        logger.error("First record has no embedding; aborting.")
        raise SystemExit(1)

# Create index if missing
existing = pc.list_indexes().names()
if INDEX_NAME not in existing:
    logger.info(f"Creating Pinecone index '{INDEX_NAME}' (dim={dim})…")
    pc.create_index(
        name=INDEX_NAME,
        dimension=dim,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV),
    )
else:
    logger.info(f"Pinecone index '{INDEX_NAME}' already exists")
index = pc.Index(INDEX_NAME)

# ─── INIT CHROMADB ─────────────────────────────────────────────────────
logger.info(f"Initializing ChromaDB at '{CHROMA_PATH}'…")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection    = chroma_client.get_or_create_collection(name=INDEX_NAME)

# ─── BACKOFF HELPERS ────────────────────────────────────────────────────
@backoff.on_exception(backoff.expo, PineconeException, max_time=60)
async def pinecone_upsert(vectors: List[Dict]):
    if not vectors:
        return
    logger.info(f"Upserting {len(vectors)} vectors to Pinecone…")
    resp = index.upsert(vectors=vectors)
    logger.debug(f"Pinecone response: {resp}")

@backoff.on_exception(backoff.expo, Exception, max_time=60)
async def chroma_add(ids: List[str], docs: List[str], metas: List[Dict]):
    if not ids:
        return
    logger.info(f"Adding {len(ids)} docs to ChromaDB…")
    collection.add(ids=ids, documents=docs, metadatas=metas)

# ─── BATCH PROCESSOR ────────────────────────────────────────────────────
async def process_batch(batch: List[Dict]):
    pc_buf, ch_ids, ch_docs, ch_meta = [], [], [], []
    for doc in batch:
        # Resolve or generate ID
        _id = doc.get("id") or doc.get("chunk_id")
        if not _id:
            meta = doc.get("metadata", {})
            _id = meta.get("id") or meta.get("chunk_index")
        if not _id:
            _id = str(uuid.uuid4())
            logger.debug(f"No ID found—generated {_id}")

        emb  = doc.get("embedding")
        text = doc.get("text", "")
        meta = doc.get("metadata", {})

        # Clean text before ingest
        text = clean_text(text)
        if not emb or not text:
            logger.debug(f"Skipping doc {_id}: missing embedding/text")
            continue
        if hasattr(emb, "tolist"):
            emb = emb.tolist()

        # Collect for Pinecone
        pc_buf.append({"id": _id, "values": emb, "metadata": meta})
        # Collect for ChromaDB
        ch_ids.append(_id)
        ch_docs.append(text)
        ch_meta.append(meta)

    # Parallel writes
    await asyncio.gather(
        pinecone_upsert(pc_buf),
        chroma_add(ch_ids, ch_docs, ch_meta),
    )

# ─── MAIN LOOP ─────────────────────────────────────────────────────────
async def main():
    count, batch = 0, []
    async with aiofiles.open(FILE_PATH, "r", encoding="utf-8") as af:
        async for line in tqdm_asyncio(af, desc="Reading & batching"):
            batch.append(json.loads(line))
            if len(batch) >= BATCH_SIZE:
                await process_batch(batch)
                count += len(batch)
                logger.info(f"✅ Processed {count} chunks…")
                batch.clear()

    # Final partial batch
    if batch:
        await process_batch(batch)
        count += len(batch)
        logger.info(f"Processed {count} chunks total")

    logger.info("All done! ")

if __name__ == "__main__":
    asyncio.run(main())
