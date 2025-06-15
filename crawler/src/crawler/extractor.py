#!/usr/bin/env python3
import logging
import warnings
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import json
import re

import tiktoken
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# PDF
from PyPDF2 import PdfReader
import pdfplumber

# DOCX
from docx import Document

# HTML extraction (your own util)
from utils import extract_main_text_from_html

# Optional semantic splitter
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    USE_SEMANTIC = True
except ImportError:
    USE_SEMANTIC = False

# ─── Suppress Noisy Warnings ─────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
warnings.filterwarnings("ignore", category=UserWarning, module="pdfplumber")
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)
logging.getLogger("PyPDF2").setLevel(logging.ERROR)
logging.getLogger("openpyxl").setLevel(logging.ERROR)

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ─── Paths & Params ───────────────────────────────────────────────────────────
RAW_BASE     = Path(r"C:\Users\Aaditya Khanal\OneDrive\Desktop\Campus_GPT\crawler\output")
HTML_DIR     = RAW_BASE / "html"
PDF_DIR      = RAW_BASE / "pdf"
DOCX_DIR     = RAW_BASE / "docx"

TEXT_DIR     = Path("pages_text/text")
OUTPUT_JSONL = Path("processed/chromadb_input.jsonl")

# Chunking parameters
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50
MIN_TOKENS    = 30

# Semantic splitter parameters
SEMANTIC_CHUNK_SIZE    = 1000
SEMANTIC_CHUNK_OVERLAP = 200

NUM_WORKERS   = 8
DEVICE        = "cuda" if torch.cuda.is_available() else "cpu"

# ─── Models ───────────────────────────────────────────────────────────────────
TOKENIZER = tiktoken.get_encoding("cl100k_base")
EMBEDDER  = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=DEVICE)

# ─── Text Cleaning ────────────────────────────────────────────────────────────
def clean_text(raw: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()

# ─── Extraction Functions ─────────────────────────────────────────────────────
def extract_text_from_pdf(fp: Path) -> str:
    # try PyPDF2 first
    try:
        reader = PdfReader(fp)
        pages = [p.extract_text() or "" for p in reader.pages]
        txt = "\n".join(pages).strip()
        if txt:
            return txt
    except Exception:
        pass
    # fallback to pdfplumber
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [pg.extract_text() or "" for pg in pdf.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        logger.error(f"PDF fallback error {fp.name}: {e}")
        return ""

def extract_text_from_docx(fp: Path) -> str:
    try:
        doc = Document(fp)
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
    except Exception as e:
        logger.error(f"DOCX extraction error {fp.name}: {e}")
        return ""

def extract_text_from_html_file(fp: Path) -> str:
    try:
        html = fp.read_text(encoding="utf-8", errors="ignore")
        return extract_main_text_from_html(html)
    except Exception as e:
        logger.error(f"HTML extraction error {fp.name}: {e}")
        return ""

# map suffix → extractor
EXTRACTORS = {
    ".pdf":  extract_text_from_pdf,
    ".doc":  extract_text_from_docx,
    ".docx": extract_text_from_docx,
    ".html": extract_text_from_html_file,
}

# ─── File-by-file conversion worker ───────────────────────────────────────────
def convert_file(fp: Path) -> Path | None:
    """
    Extract, clean, and write out cleaned text.
    Returns the Path to the .txt file, or None if skipped/empty.
    """
    extractor = EXTRACTORS.get(fp.suffix.lower())
    if not extractor:
        return None

    out_fp = TEXT_DIR / f"{fp.stem}.txt"
    # skip if already done
    if out_fp.exists():
        return out_fp

    raw = extractor(fp)
    if not raw or len(raw.strip()) < 300:
        return None

    cleaned = clean_text(raw)
    if len(cleaned) < 300:
        return None

    out_fp.write_text(cleaned, encoding="utf-8")
    return out_fp

# ─── Chunking & Embedding Helpers ────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
    if USE_SEMANTIC:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=SEMANTIC_CHUNK_SIZE,
            chunk_overlap=SEMANTIC_CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    tokens = TOKENIZER.encode(text)
    chunks, idx = [], 0
    while idx < len(tokens):
        window = tokens[idx : idx + CHUNK_SIZE]
        if len(window) >= MIN_TOKENS:
            chunks.append(TOKENIZER.decode(window))
        idx += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

# ─── Main Orchestration ──────────────────────────────────────────────────────
def main():
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    # 1) Gather only html/pdf/docx files directly from crawler output
    raw_files = []
    for d, exts in [(HTML_DIR, [".html"]),
                    (PDF_DIR,  [".pdf"]),
                    (DOCX_DIR, [".doc", ".docx"])]:
        if d.exists():
            for ext in exts:
                raw_files.extend(d.glob(f"*{ext}"))

    logger.info(f"⏳ Extracting & cleaning {len(raw_files)} files with {NUM_WORKERS} workers…")
    extracted = []

    with ProcessPoolExecutor(NUM_WORKERS) as exe:
        futures = {exe.submit(convert_file, fp): fp for fp in raw_files}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Extracting"):
            src = futures[fut]
            try:
                out_fp = fut.result()
                if out_fp:
                    extracted.append(out_fp)
            except Exception as e:
                logger.error(f"[{src.name}] extraction error: {e}")

    logger.info(f"✔️ Extraction done: {len(extracted)} cleaned files ready.")

    # 2) Chunk & batch-embed in main process (to avoid GPU contention)
    total_chunks = 0
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as out:
        for txt_fp in tqdm(sorted(extracted), desc="Indexing"):
            text = txt_fp.read_text(errors="ignore")
            chunks = chunk_text(text)
            if not chunks:
                continue

            embeddings = EMBEDDER.encode(
                chunks,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False
            )

            for chunk, emb in zip(chunks, embeddings):
                doc = {
                    "text":      chunk,
                    "embedding": emb.tolist(),
                    "metadata":  {"source": str(txt_fp)}
                }
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                total_chunks += 1

    logger.info(f"✅ Indexing complete: {len(extracted)} files → {total_chunks} chunks.")

if __name__ == "__main__":
    main()
