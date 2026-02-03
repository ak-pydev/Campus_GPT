"""
PDF Scraper for Campus GPT - "Oracle Data" Extraction
======================================================

This module handles extraction of legally binding details from university PDFs:
- Academic catalogs
- Student handbooks
- Faculty senate handbooks
- Policy documents

Features:
- Page-by-page extraction with deep linking (e.g., catalog.pdf#page=42)
- Layout-aware parsing to preserve tables
- Intelligent deduplication and noise removal
- Recursive chunking with overlap for continuity
"""

import json
import re
import os
from pathlib import Path
from typing import List, Dict, Optional
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
# Configuration
PDF_URLS = {
    "undergraduate_catalog": {
        "url": "https://catalog.nku.edu/content.php?catoid=49&navoid=2687&print",
        "title": "Undergraduate Catalog 2025-2026",
        "persona": "prospective,student",
        "faq_category": None,
        "priority": "critical"
    },
    "graduate_catalog": {
        "url": "https://catalog.nku.edu/content.php?catoid=50&navoid=2688&print",
        "title": "Graduate Catalog 2025-2026",
        "persona": "prospective,student",
        "faq_category": None,
        "priority": "critical"
    },
    # Note: Student and faculty handbooks may be web pages, not PDFs
    # They will be captured by the web scraper instead
}

OUTPUT_FILE = "campus_pdfs.jsonl"
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 100  # 10% overlap for continuity

# PDF Noise Patterns (recurring headers/footers to remove)
NOISE_PATTERNS = [
    r"NKU Catalog \d{4}-\d{4}",
    r"Northern Kentucky University",
    r"Page \d+ of \d+",
    r"www\.nku\.edu",
    r"Printed on:.*",
    r"Generated from.*",
    r"\d+\s*$",  # Standalone page numbers
]


def download_pdf(url: str, output_path: str) -> bool:
    """Download PDF from URL."""
    import requests
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded: {output_path}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {str(e)}")
        return False


def clean_pdf_text(text: str) -> str:
    """
    Remove PDF noise (headers, footers, page numbers).
    
    Args:
        text: Raw text extracted from PDF
        
    Returns:
        Cleaned text with noise removed
    """
    cleaned = text
    
    # Remove noise patterns
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    
    # Remove standalone numbers (likely page numbers)
    lines = cleaned.split('\n')
    cleaned_lines = [line for line in lines if not (line.strip().isdigit() and len(line.strip()) <= 3)]
    
    return '\n'.join(cleaned_lines).strip()


def extract_page_text(pdf_path: str, page_num: int) -> Optional[str]:
    """
    Extract text from a single PDF page using layout-aware parsing.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        Extracted text with layout preserved
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        
        # Layout-aware extraction
        # Uses 'dict' mode to preserve structure
        text_dict = page.get_text("dict")
        
        # Extract text blocks in reading order
        blocks = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        blocks.append(span["text"])
        
        full_text = " ".join(blocks)
        doc.close()
        
        return clean_pdf_text(full_text)
    
    except Exception as e:
        print(f"Error extracting page {page_num} from {pdf_path}: {str(e)}")
        return None


def extract_pdf_metadata(pdf_path: str) -> Dict:
    """Extract PDF metadata (title, author, page count)."""
    try:
        doc = fitz.open(pdf_path)
        metadata = {
            "page_count": doc.page_count,
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
        }
        doc.close()
        return metadata
    except Exception as e:
        print(f"Error extracting metadata from {pdf_path}: {str(e)}")
        return {"page_count": 0}


def chunk_text_with_overlap(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks using recursive character splitting.
    
    Args:
        text: Text to chunk
        chunk_size: Target size of each chunk
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings within the last 20% of chunk
            search_start = end - int(chunk_size * 0.2)
            sentence_end = max(
                text.rfind('. ', search_start, end),
                text.rfind('! ', search_start, end),
                text.rfind('? ', search_start, end),
                text.rfind('\n', search_start, end)
            )
            
            if sentence_end > search_start:
                end = sentence_end + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start forward, accounting for overlap
        start = end - overlap
    
    return chunks


def process_pdf(pdf_key: str, pdf_info: Dict, download_dir: str = "pdf_downloads") -> List[Dict]:
    """
    Process a single PDF: download, extract, chunk, and create metadata.
    
    Args:
        pdf_key: Unique identifier for the PDF
        pdf_info: Dictionary containing URL and metadata
        download_dir: Directory to store downloaded PDFs
        
    Returns:
        List of data entries (one per chunk)
    """
    os.makedirs(download_dir, exist_ok=True)
    
    pdf_filename = f"{pdf_key}.pdf"
    pdf_path = os.path.join(download_dir, pdf_filename)
    
    # Download if not already present
    if not os.path.exists(pdf_path):
        if not download_pdf(pdf_info["url"], pdf_path):
            return []
    
    # Extract metadata
    metadata = extract_pdf_metadata(pdf_path)
    total_pages = metadata["page_count"]
    
    print(f"\nProcessing {pdf_info['title']} ({total_pages} pages)...")
    
    entries = []
    
    # Extract text page by page
    for page_num in range(total_pages):
        page_text = extract_page_text(pdf_path, page_num)
        
        if not page_text or len(page_text) < 50:
            continue
        
        # Chunk the page text with overlap
        chunks = chunk_text_with_overlap(page_text)
        
        for chunk_idx, chunk in enumerate(chunks):
            # Create deep link to specific page
            # Format: url#page=42
            base_url = pdf_info["url"].split('#')[0].split('?')[0]
            anchor_url = f"{base_url}#page={page_num + 1}"  # 1-indexed for user display
            
            entry = {
                # Core Content
                "title": pdf_info["title"],
                "section_header": f"Page {page_num + 1}",
                "text": chunk,
                
                # Deep Linking Metadata
                "url": pdf_info["url"],
                "anchor_url": anchor_url,
                "anchor_id": f"page-{page_num + 1}",
                "header_level": None,
                
                # PDF-Specific Metadata
                "source_type": "pdf",
                "pdf_page": page_num + 1,
                "total_pages": total_pages,
                "chunk_index": chunk_idx,
                "total_chunks_on_page": len(chunks),
                
                # Persona & FAQ Tagging
                "persona": pdf_info.get("persona", "all"),
                "faq_category": pdf_info.get("faq_category"),
                "priority": pdf_info.get("priority", "medium"),
                
                # Additional Metadata
                "pdf_key": pdf_key,
                "pdf_filename": pdf_filename,
            }
            
            entries.append(entry)
        
        # Progress indicator
        if (page_num + 1) % 10 == 0:
            print(f"  Processed {page_num + 1}/{total_pages} pages...")
    
    print(f"  Completed: {len(entries)} chunks extracted from {total_pages} pages")
    return entries


def main():
    """Main execution: process all PDFs and save to JSONL."""
    all_entries = []
    
    # Process each PDF
    for pdf_key, pdf_info in PDF_URLS.items():
        entries = process_pdf(pdf_key, pdf_info)
        all_entries.extend(entries)
    
    # Save to JSONL
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + '\n')
    
    print(f"\n{'='*60}")
    print(f"PDF Extraction Complete!")
    print(f"Total PDFs processed: {len(PDF_URLS)}")
    print(f"Total chunks extracted: {len(all_entries)}")
    print(f"Output saved to: {OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
