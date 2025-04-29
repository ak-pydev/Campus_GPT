#!/usr/bin/env python3

import logging
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import json
import re

import tiktoken
import torch
from sentence_transformers import SentenceTransformer

from PyPDF2 import PdfReader
import pdfplumber

# ─── Suppress PDF warnings ────────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
warnings.filterwarnings("ignore", category=UserWarning, module="pdfplumber")
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("PyPDF2").setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ─── Paths & Params ───────────────────────────────────────────────────────────
RAW_DIR      = Path("downloads")
TEXT_DIR     = Path("pages_text/text")
OUTPUT_JSONL = Path("processed/pinecone_input.jsonl")

CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50
MIN_TOKENS    = 30
NUM_WORKERS   = 8
DEVICE        = "cuda" if torch.cuda.is_available() else "cpu"

# ─── Models ───────────────────────────────────────────────────────────────────
TOKENIZER = tiktoken.get_encoding("cl100k_base")
EMBEDDER  = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=DEVICE)

# ─── Text Cleaning ────────────────────────────────────────────────────────────
def clean_text(raw: str) -> str:
    """
    - Remove control characters
    - Collapse whitespace
    - Lowercase
    - Strip non-ASCII
    """
    # strip out any HTML artifacts (if any slipped in)
    text = re.sub(r'<[^>]+>', ' ', raw)
    # remove non-ASCII
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # lowercase for consistency
    return text.lower()

# ─── PDF Extraction ──────────────────────────────────────────────────────────
def extract_text_from_pdf(fp: Path) -> str:
    """Try PyPDF2, then pdfplumber fallback."""
    # PyPDF2 primary
    try:
        reader = PdfReader(fp)
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:
        pass
    # pdfplumber fallback
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        logging.error(f"PDF fallback error {fp.name}: {e}")
        return ""

# ─── Extraction Pipeline ─────────────────────────────────────────────────────
def convert_all():
    """
    Extract raw text from .pdf/.txt in downloads/ → pages_text/text/
    Only runs if TEXT_DIR does not already exist.
    """
    if TEXT_DIR.exists():
        logging.info("pages_text directory exists; skipping raw extraction.")
        return

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    for fp in RAW_DIR.rglob("*"):
        if not fp.is_file():
            continue

        ext = fp.suffix.lower()
        if ext == ".pdf":
            raw = extract_text_from_pdf(fp)
        elif ext == ".txt":
            raw = fp.read_text(errors="ignore")
        else:
            continue

        if raw.strip():
            cleaned = clean_text(raw)
            out = TEXT_DIR / f"{fp.stem}.txt"
            out.write_text(cleaned, encoding="utf-8")

# ─── Chunking & Embedding ────────────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
    """
    Overlapping tokenizer‐based chunks of cleaned text.
    """
    tokens = TOKENIZER.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        slice_ = tokens[start : start + CHUNK_SIZE]
        if len(slice_) >= MIN_TOKENS:
            chunk = TOKENIZER.decode(slice_)
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

def process_file(fp: Path) -> list[dict]:
    """
    Read a cleaned .txt, chunk & embed.
    Returns list of {"text","embedding","metadata"}.
    """
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    docs = []
    for chunk in chunk_text(txt):
        emb = EMBEDDER.encode(chunk, normalize_embeddings=True).tolist()
        docs.append({
            "text":      chunk,
            "embedding": emb,              # 384-dim float vector
            "metadata": {
                "source": str(fp)
            }
        })
    return docs

# ─── Indexing Pipeline ───────────────────────────────────────────────────────
def index_all():
    """
    Reads every .txt in pages_text/text/, processes them, and writes JSONL.
    """
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    files = list(TEXT_DIR.glob("*.txt"))

    with ProcessPoolExecutor(NUM_WORKERS) as exe, \
         open(OUTPUT_JSONL, "w", encoding="utf-8") as out:

        for docs in tqdm(exe.map(process_file, files), total=len(files)):
            for doc in docs:
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")

# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.info("▶️  Starting raw extraction (if needed)…")
    convert_all()

    logging.info("▶️  Starting chunking & embedding…")
    index_all()

    logging.info("✅ All done — cleaned, chunked & embedded.")
