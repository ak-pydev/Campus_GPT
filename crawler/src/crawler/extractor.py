#!/usr/bin/env python3

import logging
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import json
import re
import sys

import tiktoken
import torch
from sentence_transformers import SentenceTransformer

# PDF
from PyPDF2 import PdfReader
import pdfplumber

# DOCX
from docx import Document

# PPTX
from pptx import Presentation

# XLSX (uses openpyxl under the hood)
import pandas as pd

# HTML extraction
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
warnings.filterwarnings(
    "ignore",
    message="Unknown extension is not supported and will be removed",
    category=UserWarning,
)
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
RAW_DIR      = Path(r"C:\Users\Aaditya Khanal\OneDrive\Desktop\Campus_GPT\crawler\output")
TEXT_DIR     = Path("pages_text/text")
OUTPUT_JSONL = Path("processed/pinecone_input.jsonl")

# Chunking parameters (tune as needed)
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50
MIN_TOKENS    = 30

# Semantic splitter parameters (if USE_SEMANTIC)
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
    try:
        reader = PdfReader(fp)
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:
        pass
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
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

def extract_text_from_pptx(fp: Path) -> str:
    try:
        prs = Presentation(fp)
        texts = []
        for slide in prs.slides:
            for shp in slide.shapes:
                if hasattr(shp, "text") and shp.text:
                    texts.append(shp.text)
        return "\n".join(texts).strip()
    except Exception as e:
        logger.error(f"PPTX extraction error {fp.name}: {e}")
        return ""

def extract_text_from_xlsx(fp: Path) -> str:
    try:
        df = pd.read_excel(fp, sheet_name=None)
        rows = []
        for sheet in df.values():
            for _, row in sheet.iterrows():
                rows.append(" ".join(str(v) for v in row.values if pd.notna(v)))
        return "\n".join(rows).strip()
    except Exception as e:
        logger.error(f"XLSX extraction error {fp.name}: {e}")
        return ""

def extract_text_from_html_file(fp: Path) -> str:
    try:
        html = fp.read_text(encoding="utf-8", errors="ignore")
        return extract_main_text_from_html(html)
    except Exception as e:
        logger.error(f"HTML extraction error {fp.name}: {e}")
        return ""

# ─── Orchestrator: Raw → Cleaned Text ─────────────────────────────────────────
def convert_all():
    if TEXT_DIR.exists() and any(TEXT_DIR.glob("*.txt")):
        logger.info(f"{TEXT_DIR} already populated; skipping extraction.")
        return

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    extractors = {
        ".pdf": extract_text_from_pdf,
        ".txt": lambda fp: fp.read_text(errors="ignore"),
        ".docx": extract_text_from_docx,
        ".pptx": extract_text_from_pptx,
        ".xlsx": extract_text_from_xlsx,
        ".html": extract_text_from_html_file,
    }

    processed, skipped, errors = 0, 0, 0
    for suffix, fn in extractors.items():
        for fp in RAW_DIR.rglob(f"*{suffix}"):
            try:
                raw = fn(fp)
                if not raw or not raw.strip():
                    skipped += 1
                    continue
                cleaned = clean_text(raw)
                if len(cleaned) < 300:
                    skipped += 1
                    continue
                out = TEXT_DIR / f"{fp.stem}.txt"
                out.write_text(cleaned, encoding="utf-8")
                processed += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error processing {fp}: {e}")

    logger.info(f"Extraction complete: {processed} processed, {skipped} skipped, {errors} errors")

# ─── Chunking & Embedding ────────────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
    if USE_SEMANTIC:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=SEMANTIC_CHUNK_SIZE,
            chunk_overlap=SEMANTIC_CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    tokens = TOKENIZER.encode(text)
    chunks, start = [], 0
    while start < len(tokens):
        window = tokens[start : start + CHUNK_SIZE]
        if len(window) >= MIN_TOKENS:
            chunks.append(TOKENIZER.decode(window))
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

def process_file(fp: Path) -> list[dict]:
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    docs = []
    for chunk in chunk_text(txt):
        emb = EMBEDDER.encode(chunk, normalize_embeddings=True).tolist()
        docs.append({
            "text":      chunk,
            "embedding": emb,
            "metadata":  {"source": str(fp)},
        })
    return docs

# ─── Indexing Pipeline ───────────────────────────────────────────────────────
def index_all():
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    files = list(TEXT_DIR.glob("*.txt"))
    total_chunks = 0

    with ProcessPoolExecutor(NUM_WORKERS) as exe, open(OUTPUT_JSONL, "w", encoding="utf-8") as out:
        for docs in tqdm(exe.map(process_file, files, chunksize=10), total=len(files)):
            for doc in docs:
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            total_chunks += len(docs)

    logger.info(f"Indexing complete: {len(files)} files → {total_chunks} chunks to {OUTPUT_JSONL}")

if __name__ == "__main__":
    logger.info("▶️  Starting extraction & cleaning…")
    convert_all()
    logger.info("▶️  Starting chunking & embedding…")
    index_all()
    logger.info("✅ All done.")
