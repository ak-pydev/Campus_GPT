# PDF Scraping Strategy - "Oracle Data" Extraction

## Why PDFs Are Critical

Websites often summarize policies, but **PDFs contain the legally binding details** that students, faculty, and staff rely on for accurate information.

### The "Oracle" Data Sources

1. **Academic Catalog** - Crucial for answering:
   - "What classes do I need to graduate?"
   - "What are the prerequisites for this course?"
   - "What's the GPA requirement for my major?"

2. **Student Handbook** - Essential for:
   - Code of conduct policies
   - Disciplinary procedures
   - Student rights and responsibilities

3. **Faculty Senate Handbooks** - Necessary for:
   - University operator guidelines
   - Faculty rules and governance
   - Academic policies

---

## The "Interactive PDF" Strategy

### 1. The "Deep Link" Method

Instead of just saying "I found this in a PDF," the chatbot provides a **direct link to the specific page**.

**Implementation**:

- Extract text page-by-page using PyMuPDF
- Store source URL with page anchor: `nku.edu/catalog.pdf#page=42`
- Create metadata linking each chunk to its exact page

**Example**:

```
Student Query: "What are the requirements for a Computer Science major?"

Bot Response: "The Computer Science major requires..."

Sources & Quick Links:
- [Undergraduate Catalog - Computer Science Requirements](https://catalog.nku.edu/undergraduate.pdf#page=125)
```

The link opens the catalog directly to page 125.

### 2. Layout-Aware Parsing

University catalogs often contain:

- Multi-column layouts
- Complex tables (course listings, degree requirements)
- Structured data that standard scrapers scramble

**Solution**: Use PyMuPDF's layout-aware extraction with `get_text("dict")` mode.

**Benefits**:

- Preserves table structures
- Maintains column order
- Keeps "Credit Hours" separate from "Prerequisites"
- Ensures accurate course information

**Research Paper Novelty**: Mention using **Layout-Aware Extraction** to preserve structural integrity of academic documents.

---

## PDF Noise Removal

PDFs are full of recurring elements that confuse RAG systems:

- Headers: "NKU Catalog 2025-2026"
- Footers: "www.nku.edu"
- Page numbers: "Page 42 of 300"
- Metadata: "Printed on: 2025-09-01"

### The Deduplication Step

My `pdf_scraper.py` includes intelligent noise removal:

```python
NOISE_PATTERNS = [
    r"NKU Catalog \d{4}-\d{4}",
    r"Northern Kentucky University",
    r"Page \d+ of \d+",
    r"www\.nku\.edu",
    r"Printed on:.*",
]
```

**Benefits**:

- Reduces token cost
- Keeps model focused on actual policy content
- Improves retrieval accuracy

---

## Chunking Strategy

### Recursive Character Splitting with 10% Overlap

**Why Overlap Is Critical**:
A policy that starts at the bottom of page 10 and continues on page 11 shouldn't be cut in half.

**Implementation**:

```python
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 100  # 10% overlap
```

**How It Works**:

1. Split text into ~1000 character chunks
2. Create 100-character overlap between chunks
3. Break at sentence boundaries when possible
4. Preserve continuity across page breaks

**Example**:

```
Chunk 1: "...students must maintain a 2.5 GPA. Additionally, all students..."

Chunk 2 (starts with overlap): "...all students must complete 120 credit hours..."
```

The overlap ensures context isn't lost.

---

## PDF URLs and Priorities

### Configured PDFs

```python
PDF_URLS = {
    "undergraduate_catalog": {
        "url": "https://catalog.nku.edu/undergraduate.pdf",
        "priority": "critical",
        "persona": "prospective,student"
    },
    "graduate_catalog": {
        "url": "https://catalog.nku.edu/graduate.pdf",
        "priority": "critical",
        "persona": "prospective,student"
    },
    "student_handbook": {
        "url": "https://inside.nku.edu/handbook.pdf",
        "priority": "high",
        "persona": "student"
    },
    "faculty_handbook": {
        "url": "https://inside.nku.edu/faculty_handbook.pdf",
        "priority": "medium",
        "persona": "faculty"
    }
}
```

### Priority Levels

- **Critical**: Academic catalogs (re-scrape before each semester)
- **High**: Student/faculty handbooks (re-scrape annually)
- **Medium**: Policy documents (re-scrape when updated)

---

## Output Format

Each PDF chunk is saved with comprehensive metadata:

```json
{
  "title": "Undergraduate Catalog 2025-2026",
  "section_header": "Page 125",
  "text": "Computer Science Major Requirements: Students must complete...",

  "url": "https://catalog.nku.edu/undergraduate.pdf",
  "anchor_url": "https://catalog.nku.edu/undergraduate.pdf#page=125",
  "anchor_id": "page-125",

  "source_type": "pdf",
  "pdf_page": 125,
  "total_pages": 300,
  "chunk_index": 0,

  "persona": "prospective,student",
  "priority": "critical",
  "pdf_key": "undergraduate_catalog"
}
```

---

## Usage

### Installation

```bash
pip install PyMuPDF requests
```

### Run PDF Scraper

```bash
cd 01_crawling
python pdf_scraper.py
```

### Output

- Downloads PDFs to `pdf_downloads/` directory
- Extracts and cleans text page-by-page
- Chunks with 10% overlap
- Saves to `campus_pdfs.jsonl`

### Expected Results

```
Processing Undergraduate Catalog 2025-2026 (450 pages)...
  Processed 100/450 pages...
  Processed 200/450 pages...
  ...
  Completed: 2,341 chunks extracted from 450 pages

Processing Graduate Catalog 2025-2026 (280 pages)...
  ...
  Completed: 1,456 chunks extracted from 280 pages

============================================================
PDF Extraction Complete!
Total PDFs processed: 4
Total chunks extracted: 5,234
Output saved to: campus_pdfs.jsonl
============================================================
```

---

## Integration with RAG System

### Combine with Web Scraping Data

```python
# Merge PDF and web data
import json

# Load web scraping data
web_data = []
with open('campus_data.jsonl', 'r') as f:
    web_data = [json.loads(line) for line in f]

# Load PDF data
pdf_data = []
with open('campus_pdfs.jsonl', 'r') as f:
    pdf_data = [json.loads(line) for line in f]

# Combine
all_data = web_data + pdf_data

# Save combined
with open('combined_campus_data.jsonl', 'w') as f:
    for entry in all_data:
        f.write(json.dumps(entry) + '\n')
```

### Vector Store Ingestion

Update your RAG system to handle PDF metadata:

```python
collection.add(
    documents=[data["text"]],
    metadatas=[{
        "title": data["title"],
        "url": data.get("anchor_url", data["url"]),
        "source_type": data.get("source_type", "web"),
        "pdf_page": data.get("pdf_page"),
        "persona": data.get("persona", "all"),
    }],
    ids=[f"{data.get('pdf_key', 'web')}_{data.get('pdf_page', 0)}_{data.get('chunk_index', 0)}"]
)
```

### Response Formatting

When the bot retrieves PDF content, format with page-specific links:

```
Answer: The Computer Science major requires 120 credit hours...

Sources & Quick Links:
- [Undergraduate Catalog - Page 125](https://catalog.nku.edu/undergraduate.pdf#page=125)
- [CS Department Requirements - Page 128](https://catalog.nku.edu/undergraduate.pdf#page=128)
```

---

## Research Paper Contributions

Highlight these novelties in your paper:

### 1. Hybrid Retrieval Approach

- Combines web scraping with PDF extraction
- Maintains dual source types for comprehensive coverage

### 2. Layout-Aware PDF Parsing

- Preserves table structures in academic catalogs
- Prevents information scrambling in multi-column layouts
- Uses PyMuPDF's dictionary mode for structural integrity

### 3. Deep Linking to PDF Pages

- Provides direct navigation to specific pages
- Enhances user experience with precise citations
- Reduces time to find information

### 4. Intelligent Noise Removal

- Pattern-based deduplication for PDF artifacts
- Reduces token costs and improves retrieval accuracy
- Custom cleaning pipeline for university documents

### 5. Context-Preserving Chunking

- Recursive character splitting with 10% overlap
- Sentence-boundary aware splitting
- Prevents loss of context across page breaks

---

## Best Practices

### 1. Re-scraping Schedule

- **Academic Catalogs**: Before Fall and Spring semesters
- **Student Handbook**: Annually or when policies change
- **Faculty Documents**: When updated by administration

### 2. PDF Validation

After scraping, validate:

- Page count matches expected
- No blank chunks
- Noise patterns removed
- Overlap functioning correctly

### 3. Monitor Updates

Set up alerts for PDF updates:

```bash
# Check if PDF modified
curl -I https://catalog.nku.edu/undergraduate.pdf | grep Last-Modified
```

### 4. Backup Original PDFs

Always keep original PDFs:

- For reference
- For re-processing with improved algorithms
- For legal compliance

---

## Troubleshooting

### Issue: PyMuPDF Not Installed

```bash
pip install PyMuPDF
```

### Issue: Download Fails

Check URL accessibility:

```bash
curl -I https://catalog.nku.edu/undergraduate.pdf
```

### Issue: Text Scrambled

- Verify using `get_text("dict")` mode
- Check if PDF is scanned image (needs OCR)
- Try alternative extraction method

### Issue: Too Many Small Chunks

Increase `CHUNK_SIZE`:

```python
CHUNK_SIZE = 1500  # Increase from 1000
```

---

## Next Steps

1. **Run PDF scraper**: `python pdf_scraper.py`
2. **Validate output**: Check `campus_pdfs.jsonl`
3. **Merge with web data**: Combine JSONL files
4. **Update RAG system**: Ingest combined data
5. **Test PDF responses**: Query catalog-specific questions

---

**Note**: This PDF scraping strategy ensures legally binding "oracle data" is accessible through my RAG system with precise page-level citations, maintaining accuracy and transparency in all university policy responses.
