#!/usr/bin/env python3
import io
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
from bs4 import BeautifulSoup

# PDF
from pypdf import PdfReader
import pdfplumber

# DOCX (ensure python-docx is installed)
from docx import Document

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
RAW_BASE     = Path("../../output")  # Relative path from src/crawler
HTML_DIR     = RAW_BASE / "html"
PDF_DIR      = RAW_BASE / "pdf"
DOCX_DIR     = RAW_BASE / "docx"
TEXT_DIR     = RAW_BASE / "text"

OUTPUT_JSONL = Path("../../processed/chromadb_input.jsonl")

# Chunking parameters
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50
MIN_TOKENS    = 30

# Semantic splitter parameters (optional)
SEMANTIC_CHUNK_SIZE    = 1000
SEMANTIC_CHUNK_OVERLAP = 200
USE_SEMANTIC           = False  # Toggle for semantic vs token-based chunking

NUM_WORKERS   = 8
DEVICE        = "cuda" if torch.cuda.is_available() else "cpu"

# ─── Models ───────────────────────────────────────────────────────────────────
TOKENIZER = tiktoken.get_encoding("cl100k_base")
EMBEDDER  = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=DEVICE)

# ─── Text Cleaning ────────────────────────────────────────────────────────────
def clean_html(raw_html: str) -> str:
    """
    Use BeautifulSoup to strip tags and extract main content (headings, paragraphs, lists).
    """
    soup = BeautifulSoup(raw_html, "lxml")
    # remove boilerplate
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    # collect headings and text
    pieces = []
    for el in soup.find_all(["h1","h2","h3","h4","h5","h6","p","li"]):
        txt = el.get_text(separator=" ", strip=True)
        if txt:
            pieces.append(txt)
    joined = " ".join(pieces)
    cleaned = re.sub(r"\s+", " ", joined).strip().lower()
    return cleaned

# ─── Extraction Functions ─────────────────────────────────────────────────────
def extract_text_from_pdf(fp: Path) -> str:
    try:
        reader = PdfReader(fp)
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [pg.extract_text() or "" for pg in pdf.pages]
        return "\n".join(pages)
    except Exception as e:
        logger.error(f"PDF fallback error {fp.name}: {e}")
        return ""


def extract_text_from_docx(fp: Path) -> str:
    try:
        doc = Document(fp)
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    except Exception as e:
        logger.error(f"DOCX extraction error {fp.name}: {e}")
        return ""


def extract_text_from_html_file(fp: Path) -> str:
    try:
        html = fp.read_text(encoding="utf-8", errors="ignore")
        return clean_html(html)
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

# ─── File Conversion Worker ────────────────────────────────────────────────────
def convert_file(fp: Path) -> Path | None:
    extractor = EXTRACTORS.get(fp.suffix.lower())
    if not extractor:
        return None
    out_fp = TEXT_DIR / f"{fp.stem}.txt"
    if out_fp.exists():
        return out_fp
    raw = extractor(fp)
    if not raw or len(raw) < 300:
        return None
    cleaned = raw.lower()
    out_fp.write_text(cleaned, encoding="utf-8")
    return out_fp

# ─── Chunking & Embedding Helpers ────────────────────────────────────────────
def chunk_text(text: str) -> list[str]:
    if USE_SEMANTIC:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=SEMANTIC_CHUNK_SIZE,
            chunk_overlap=SEMANTIC_CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)
    tokens = TOKENIZER.encode(text)
    chunks, idx = [], 0
    while idx < len(tokens):
        window = tokens[idx:idx+CHUNK_SIZE]
        if len(window) >= MIN_TOKENS:
            chunks.append(TOKENIZER.decode(window))
        idx += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

# ─── Main Orchestration ──────────────────────────────────────────────────────
def main():
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    raw_files = []
    for d, exts in [(HTML_DIR, ['.html']), (PDF_DIR, ['.pdf']), (DOCX_DIR, ['.doc', '.docx'])]:
        if d.exists():
            for ext in exts:
                raw_files.extend(d.glob(f"*{ext}"))

    logger.info(f"⏳ Processing {len(raw_files)} files with {NUM_WORKERS} workers…")
    extracted = []
    with ProcessPoolExecutor(NUM_WORKERS) as exe:
        futures = {exe.submit(convert_file, fp): fp for fp in raw_files}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Extracting"):
            fp = futures[fut]
            try:
                out_fp = fut.result()
                if out_fp:
                    extracted.append(out_fp)
            except Exception as e:
                logger.error(f"[{fp.name}] error: {e}")

    logger.info(f"  Converted: {len(extracted)} text files ready.")
    total_chunks = 0
    with open(OUTPUT_JSONL, 'w', encoding='utf-8') as out:
        for txt_fp in tqdm(sorted(extracted), desc="Indexing"):
            text = txt_fp.read_text(errors="ignore")
            for chunk in chunk_text(text):
                emb = EMBEDDER.encode(chunk, normalize_embeddings=True).tolist()
                out.write(json.dumps({
                    'text': chunk,
                    'embedding': emb,
                    'metadata': {'source': str(txt_fp)}
                }, ensure_ascii=False) + '\n')
                total_chunks += 1
    logger.info(f" Done: {len(extracted)} files → {total_chunks} chunks.")

if __name__ == '__main__':
    main()
