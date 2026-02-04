# Master Scraper Usage Guide

## Quick Start

Run both web and PDF scrapers in parallel with a single command:

```bash
cd 01_crawling
python master_scraper.py
```

That's it! The master scraper will:

1. Run web scraping and PDF extraction in parallel
2. Show real-time progress for both
3. Automatically merge results into `combined_campus_data.jsonl`

## What Happens

### Parallel Processing

```
CAMPUS GPT MASTER SCRAPER
Running Web + PDF Scrapers in Parallel
============================================================

============================================================
STARTING WEB SCRAPER
============================================================
[*] (1/1000) Scraping: https://www.nku.edu...

============================================================
STARTING PDF SCRAPER
============================================================
Downloading: pdf_downloads/undergraduate_catalog.pdf
Processing Undergraduate Catalog 2025-2026 (450 pages)...
```

Both scrapers run simultaneously for maximum speed!

### Output Files

After completion, you'll have three files:

1. **`campus_data.jsonl`** - Web scraping results (HTML pages)
2. **`campus_pdfs.jsonl`** - PDF extraction results (catalogs, handbooks)
3. **`combined_campus_data.jsonl`** - Merged dataset for RAG system

### Final Summary

```
============================================================
SCRAPING COMPLETE - SUMMARY
============================================================

WEB Scraper: ✓ SUCCESS
  Time: 285.43 seconds

PDF Scraper: ✓ SUCCESS
  Time: 156.78 seconds

DATA COLLECTED:
  Web entries: 3,247
  PDF entries: 5,234
  Total entries: 8,481

OUTPUT FILES:
  Web: campus_data.jsonl
  PDF: campus_pdfs.jsonl
  Combined: combined_campus_data.jsonl

TOTAL TIME: 287.12 seconds
============================================================
```

Note: Total time is ~287 seconds instead of 442 seconds (285+156) because they ran in parallel!

## Merge Only Mode

If you've already scraped but want to regenerate the combined dataset (e.g., after updating error filtering):

```bash
cd 01_crawling
python master_scraper.py --merge-only
```

This will:

- Skip re-scraping
- Filter out error pages (404, "Page Not Found")
- Regenerate clean `combined_campus_data.jsonl`
- Show filtered count

```
============================================================
MERGE-ONLY MODE: Regenerating Combined Dataset
============================================================

Loaded 3247 entries from web scraper (35 error pages filtered)
Loaded 5234 entries from PDF scraper (0 error pages filtered)

Saved 8446 total entries to combined_campus_data.jsonl
Filtered out 35 error pages

============================================================
✅ MERGE COMPLETE
============================================================
Web entries: 3247
PDF entries: 5234
Error pages filtered: 35
Total valid entries: 8446
```

## Alternative: Run Separately

If you prefer to run them separately:

### Web Scraper Only

```bash
python scraper.py
```

### PDF Scraper Only

```bash
python pdf_scraper.py
```

### Manual Merge

```python
python -c "
import json
web = [json.loads(l) for l in open('campus_data.jsonl')]
pdf = [json.loads(l) for l in open('campus_pdfs.jsonl')]
with open('combined_campus_data.jsonl', 'w') as f:
    for entry in web + pdf:
        f.write(json.dumps(entry) + '\n')
"
```

## Recommended: Use Master Scraper

The `master_scraper.py` is recommended because:

- **Faster**: Parallel execution saves time
- **Convenient**: Single command
- **Auto-merge**: Automatically combines outputs
- **Error filtering**: Removes 404 and error pages during merge
- **Better logging**: Comprehensive progress tracking
- **Merge-only mode**: Quick re-merge without re-scraping

## Next Steps

After running the master scraper:

1. **Verify output**: Check `combined_campus_data.jsonl` exists
2. **Update RAG**: Run ingestion to load new data
   ```bash
   uv run python 02_rag_system/main.py ingest
   ```
3. **Test**: Query the system with catalog questions
   ```bash
   uv run python 02_rag_system/main.py qa
   ```

## Configuration

Both scrapers can be configured independently:

### Web Scraper (`scraper.py`)

- `MAX_PAGES`: Number of pages to scrape (default: 1000)
- `ALLOWED_DOMAINS`: List of NKU domains to crawl
- `START_URL`: Starting point for crawling

### PDF Scraper (`pdf_scraper.py`)

- `PDF_URLS`: Dictionary of PDFs to extract
- `CHUNK_SIZE`: Characters per chunk (default: 1000)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 100)

## Troubleshooting

### Import Error

If you get `ModuleNotFoundError`, make sure you're in the `01_crawling` directory:

```bash
cd 01_crawling
python master_scraper.py
```

### One Scraper Fails

The master scraper will still complete if one fails. Check the summary to see which succeeded.

### Out of Memory

If running both in parallel causes memory issues, run them separately instead.

---

**Recommendation**: Use `master_scraper.py` for comprehensive, efficient data collection!
