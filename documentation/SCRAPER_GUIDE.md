# Enhanced Scraper Implementation Guide

## Overview

The updated `scraper.py` now extracts **header anchors** and creates **section-level chunks** with deep linking, persona tagging, and FAQ categorization. This enables interactive, accurate responses with clickable citations.

---

## Key Features

### 1. **Markdown-First Scraping** 

- **What**: Uses Crawl4AI to preserve header hierarchy (`#`, `##`, `###`)
- **Why**: LLMs understand structured content better than raw HTML
- **Benefit**: Distinguishes "Undergraduate Tuition" from "Graduate Tuition" by header proximity

### 2. **URL and Anchor Metadata** 

- **Deep Linking**: Saves `anchor_url` like `nku.edu/admissions#deadlines`
- **Header IDs**: Extracts `<h2 id="deadlines">`  stores as `#deadlines`
- **Benefit**: Interactive chatbot can link to specific sections, not just pages

### 3. **Persona Tagging** 

- **Auto-Detection**: URLs tagged as `faculty`, `student`, `prospective`, `financial`, `housing`, or `all`
- **Pattern Matching**:
  - `/financial-aid`  `financial`
  - `/canvas`  `student`
  - `/faculty`  `faculty`
- **Benefit**: RAG can filter results by audience ("Show me student resources")

### 4. **FAQ Quick Links** 

- **Fast Track**: High-traffic questions bypass RAG for instant, accurate answers
- **Example**: "Where is the campus map?"  Direct link to `nku.edu/map`
- **Implementation**: See `faq_matcher.py` (included)

### 5. **Section-Level Chunking** 

- **Granular Storage**: Each header section saved as separate entry
- **Metadata**: Includes `section_header`, `anchor_id`, `header_level`
- **Benefit**: More precise retrieval ("Get the 'Deadlines' section from Admissions")

---

## Data Structure

### Output Format (JSONL)

Each line in `campus_data.jsonl` now contains:

```json
{
  // Core Content
  "title": "Admissions | Northern Kentucky University",
  "section_header": "Application Deadlines",
  "text": "## Application Deadlines\n\n- Fall 2026: August 1, 2026\n- Spring 2027: December 1, 2026",

  // Deep Linking
  "url": "https://www.nku.edu/admissions",
  "anchor_url": "https://www.nku.edu/admissions#deadlines",
  "anchor_id": "deadlines",
  "header_level": "h2",

  // Persona & FAQ
  "persona": "prospective",
  "faq_category": null,

  // Metadata
  "chunk_index": 2,
  "total_chunks": 5,
  "page_scraped_at": "2026-02-03T18:00:00Z"
}
```

### Key Fields Explained

| Field            | Description                  | Example                                   |
| ---------------- | ---------------------------- | ----------------------------------------- |
| `section_header` | Header text for this section | "Application Deadlines"                   |
| `anchor_url`     | Deep link with #anchor       | `nku.edu/admissions#deadlines`            |
| `anchor_id`      | HTML ID attribute            | `"deadlines"`                             |
| `persona`        | Target audience              | `"prospective"`, `"student"`, `"faculty"` |
| `faq_category`   | FAQ quick link match         | `"map"`, `"tuition"`, `null`              |
| `chunk_index`    | Section position on page     | `2` (3rd section, 0-indexed)              |

---

## Integration with RAG System

### Step 1: Update Vector Store Metadata

When loading data into ChromaDB (or your vector store), include the new metadata:

```python
import json
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="campus_gpt")

with open("campus_data.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)

        collection.add(
            documents=[data["text"]],
            metadatas=[{
                "title": data["title"],
                "section_header": data.get("section_header", ""),
                "url": data["url"],
                "anchor_url": data.get("anchor_url", data["url"]),  # Use anchor URL
                "persona": data.get("persona", "all"),
                "faq_category": data.get("faq_category"),
            }],
            ids=[f"{data['url']}_{data.get('chunk_index', 0)}"]
        )
```

### Step 2: Modify RAG Retrieval

Add persona filtering and anchor URL preference:

```python
def retrieve_context(query, persona=None, top_k=5):
    """
    Retrieve relevant context with optional persona filtering.
    """
    # Optional: Check FAQ quick links first
    from faq_matcher import match_faq_quick_link
    quick_link = match_faq_quick_link(query, threshold=0.85)
    if quick_link:
        return {
            "type": "quick_link",
            "url": quick_link["url"],
            "title": quick_link["title"],
            "description": quick_link["description"]
        }

    # Standard RAG retrieval
    where_filter = {"persona": persona} if persona else None

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter  # Filter by persona
    )

    # Extract context with anchor URLs
    contexts = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]
        contexts.append({
            "text": doc,
            "section": metadata.get("section_header", ""),
            "url": metadata.get("anchor_url", metadata["url"]),  # Prefer anchor URL
            "title": metadata["title"]
        })

    return contexts
```

### Step 3: Format Interactive Responses

Update your LLM prompt to generate clickable citations:

```python
def format_response_with_citations(answer, contexts):
    """
    Add 'Sources & Quick Links' section to chatbot response.
    """
    citations = []
    for ctx in contexts:
        section_info = f" - {ctx['section']}" if ctx['section'] else ""
        citations.append(f"- [{ctx['title']}{section_info}]({ctx['url']})")

    citations_text = "\n".join(citations)

    return f"""{answer}

---

###  Sources & Quick Links
{citations_text}
"""
```

### Step 4: System Prompt Enhancement

Add this to your LLM system prompt:

```
When answering questions, always conclude with a "Sources & Quick Links" section.
Format citations as markdown links: [Page Title - Section](URL).
If the information comes from a specific section, use the provided anchor link.

Example:
"...you can find this on the admissions page.

###  Sources & Quick Links
- [Admissions - Application Deadlines](https://nku.edu/admissions#deadlines)
- [Financial Aid - Costs](https://nku.edu/financialaid#costs)"
```

---

## FAQ Quick Links Usage

### Integration Example

```python
from faq_matcher import match_faq_quick_link, format_quick_link_response

def handle_query(user_query):
    # 1. Try FAQ quick link first (90% similarity bypass)
    faq_match = match_faq_quick_link(user_query, threshold=0.85)

    if faq_match:
        return format_quick_link_response(faq_match)

    # 2. Standard RAG pipeline
    contexts = retrieve_context(user_query)
    answer = generate_answer(user_query, contexts)

    return format_response_with_citations(answer, contexts)
```

### Test the FAQ Matcher

```bash
cd 01_crawling
python faq_matcher.py
```

Expected output:

```
Query: 'Where is the campus map?'
 MATCH: NKU Campus Map (95% confidence)
  URL: https://www.nku.edu/map

Query: 'Tell me about admission requirements'
 No quick link match - will use RAG retrieval
```

---

## Running the Enhanced Scraper

### Prerequisites

```bash
pip install crawl4ai beautifulsoup4
```

### Execute

```bash
cd 01_crawling
python scraper.py
```

### Expected Output

```
[*] (1/1000) Scraping: https://www.nku.edu...
    -> Saved 4 sections with 3 anchors (persona: all).

[*] (2/1000) Scraping: https://www.nku.edu/admissions...
    -> Saved 7 sections with 5 anchors (persona: prospective).

...

[+] Crawl complete. 150 pages scraped, 523 sections saved to campus_data.jsonl
[+] Each section includes anchor URLs for deep linking and persona tags for targeted responses.
```

---

## Best Practices

### 1. **Re-scraping Schedule**

- **Critical Pages**: Re-scrape "Dates & Deadlines" daily (cron job)
- **Static Pages**: Re-scrape quarterly
- **Prevents**: "Conflicting truth" issues (outdated registration dates)

```bash
# Cron job example (Linux/macOS)
0 2 * * * cd /path/to/Campus_GPT/01_crawling && python scraper.py
```

### 2. **Sitemap Crawling**

Currently using **link-following**. For comprehensive coverage, use **sitemap.xml**:

```python
# Future enhancement: Add sitemap parsing
import xml.etree.ElementTree as ET
import requests

def load_sitemap_urls(sitemap_url):
    response = requests.get(sitemap_url)
    root = ET.fromstring(response.content)

    urls = []
    for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is not None:
            urls.append(loc.text)

    return urls
```

### 3. **Persona-Specific Overrides**

For certain queries, force a persona filter:

```python
persona_keywords = {
    "student": ["canvas", "mynku", "register", "schedule"],
    "faculty": ["teaching", "research", "grants"],
    "prospective": ["apply", "tour", "visit", "admissions"]
}

def detect_query_persona(query):
    query_lower = query.lower()
    for persona, keywords in persona_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return persona
    return None

# Usage
query = "How do I access Canvas?"
persona = detect_query_persona(query)  # Returns "student"
contexts = retrieve_context(query, persona=persona)
```

---

## Troubleshooting

### Issue: Anchor URLs Not Found

**Cause**: Page headers don't have `id` attributes
**Solution**: Headers without IDs will use base URL (still functional)

### Issue: Too Many Sections

**Cause**: Pages with 20+ headers create noise
**Solution**: Adjust minimum content length in `create_section_chunks()`:

```python
if len(section_text) > 100:  # Increase from 50 to 100
```

### Issue: Persona Mismatch

**Cause**: URL pattern not in `PERSONA_PATTERNS`
**Solution**: Add new patterns to `scraper.py`:

```python
PERSONA_PATTERNS = {
    "faculty": ["/faculty", "/staff", "/employee", "/academic", "/research"],  # Added /research
    ...
}
```

---

## Next Steps

1. **Update RAG System**: Modify `02_rag_system/main.py` to use new metadata fields
2. **Test FAQ Matcher**: Run `python faq_matcher.py` and verify quick link matches
3. **Re-run Scraper**: Execute `python scraper.py` to regenerate `campus_data.jsonl`
4. **Update Vector Store**: Re-index data with new metadata fields
5. **Test Interactive Responses**: Verify anchor links work in chatbot UI

---

## Summary of Changes

| Feature       | Before        | After                                   |
| ------------- | ------------- | --------------------------------------- |
| **Chunking**  | Full page     | Section-level (per header)              |
| **URLs**      | Base URL only | `anchor_url` with `#section`            |
| **Metadata**  | Title + URL   | + persona, FAQ, anchor ID, header level |
| **Retrieval** | Generic       | Persona-filtered + FAQ fast track       |
| **Citations** | Page links    | Deep links to specific sections         |

**Result**: More precise, interactive, and user-friendly RAG chatbot! 
