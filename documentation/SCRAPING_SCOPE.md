# NKU Web Scraping Scope & Strategy

This document outlines the comprehensive web scraping strategy for Campus GPT, targeting the full Northern Kentucky University digital ecosystem.

## Scraping Domains

### 1. Primary Public Site (`nku.edu` / `www.nku.edu`)

**Purpose**: The main site serves as the public face for prospective students and the general community.

**Key Content Areas**:

- Admissions information and requirements
- Academic programs overview
- Campus life and student services
- Athletics and events
- General university information

**Target Pages**:

- `/admissions` - Application processes, deadlines, requirements
- `/academics` - Program listings, departments, colleges
- `/future-students` - Prospective student resources
- `/current-students` - Student resources and services
- `/campus-life` - Housing, dining, activities
- `/about` - University history, mission, leadership

**Persona Tags**: `prospective`, `all`

---

### 2. Inside NKU (`inside.nku.edu`)

**Purpose**: Internal portal housing the vast majority of internal resources, including departmental information, student resources, and university policies.

**Key Content Areas**:

- Departmental pages and contacts
- Internal policies and procedures
- Faculty and staff resources
- Administrative information
- Student success resources

**Target Pages**:

- Department homepages
- Policy documents
- Faculty/staff directories
- Resource centers

**Persona Tags**: `faculty`, `student`, `all`

**Note**: May require authentication for some content. The scraper will capture publicly accessible pages.

---

### 3. Academic Catalogs (`catalog.nku.edu`, `undergrad.catalog.nku.edu`, `graduate.catalog.nku.edu`)

**Purpose**: The undergraduate and graduate catalogs consist of hundreds of digital pages detailing every course and program offered at Northern Kentucky University.

**Key Content Areas**:

- Complete course listings with descriptions
- Degree requirements
- Program curricula
- Academic policies
- Prerequisite chains

**Target Pages**:

- Course catalogs by department
- Degree program requirements
- Academic regulations
- Transfer credit policies

**Persona Tags**: `student`, `prospective`, `all`

**Special Handling**:

- High-value content for RAG system
- Section-level chunking critical for course lookups
- Anchor links important for direct course references

---

### 4. Service Portals (`mynku.nku.edu`)

**Purpose**: Extensive systems like myNKU provide deep, personalized content for thousands of students and faculty at Northern Kentucky University.

**Key Content Areas**:

- Student portal access information
- Login instructions
- Portal features overview
- Quick links to services

**Target Pages**:

- Portal landing pages
- Help and support pages
- Service descriptions

**Persona Tags**: `student`, `faculty`

**Note**: Cannot scrape authenticated content (Canvas, personal dashboards). Focus on publicly available information about accessing these services.

---

### 5. IT Service Desk Knowledge Base (`kb.nku.edu`)

**Purpose**: Thousands of help articles available through the IT Service Desk Knowledge Base.

**Key Content Areas**:

- Technical support articles
- How-to guides
- Troubleshooting steps
- Software and system documentation
- Common issues and solutions

**Target Pages**:

- All KB articles
- Category pages
- Search-optimized help content

**Persona Tags**: `student`, `faculty`, `all`

**FAQ Integration**: Many KB articles are high-traffic and should be indexed for quick FAQ responses.

---

### 6. Campus News (`news.nku.edu`)

**Purpose**: Numerous campus news updates added regularly at Northern Kentucky University.

**Key Content Areas**:

- University announcements
- Event coverage
- Achievement highlights
- Policy changes
- Campus updates

**Target Pages**:

- Recent news articles
- Event announcements
- Press releases

**Persona Tags**: `all`

**Special Handling**:

- Date-sensitive content
- Requires regular re-scraping (daily or weekly)
- Important for keeping information current

---

## Scraping Configuration

### Current Settings

```python
START_URL = "https://www.nku.edu"
MAX_PAGES = 1000

ALLOWED_DOMAINS = [
    "nku.edu",
    "www.nku.edu",
    "inside.nku.edu",
    "catalog.nku.edu",
    "undergrad.catalog.nku.edu",
    "graduate.catalog.nku.edu",
    "mynku.nku.edu",
    "kb.nku.edu",
    "news.nku.edu",
]
```

### Recommendations

**For Comprehensive Coverage**:

- Increase `MAX_PAGES` to 5000+ for initial full scrape
- Run domain-specific crawls for catalogs (start from catalog URLs)
- Set up scheduled re-scraping for news and KB

**Priority Levels**:

1. **Critical** (weekly re-scrape): Academic catalogs, admissions, financial aid
2. **High** (bi-weekly): KB articles, current student resources
3. **Medium** (monthly): Departmental pages, faculty resources
4. **Low** (quarterly): General university info, historical content

---

## Content Volume Estimates

| Domain          | Estimated Pages | Priority | Re-scrape Frequency          |
| --------------- | --------------- | -------- | ---------------------------- |
| www.nku.edu     | 500-1000        | Critical | Weekly                       |
| inside.nku.edu  | 1000-2000       | High     | Bi-weekly                    |
| catalog.nku.edu | 500-800         | Critical | Weekly (during registration) |
| kb.nku.edu      | 500-1000        | High     | Weekly                       |
| news.nku.edu    | 200-500         | Medium   | Daily                        |
| **Total**       | **2700-5300**   | -        | -                            |

---

## Implementation Strategy

### Phase 1: Initial Broad Crawl (Current)

- Start from `www.nku.edu`
- Follow all internal links within allowed domains
- Capture 1000 most important pages
- **Status**: Implemented

### Phase 2: Domain-Specific Targeted Crawls

- Run separate crawls for each major domain
- Start URLs:
  ```python
  DOMAIN_START_URLS = [
      "https://www.nku.edu",
      "https://inside.nku.edu",
      "https://catalog.nku.edu",
      "https://kb.nku.edu",
      "https://news.nku.edu",
  ]
  ```
- Ensure comprehensive coverage of each area

### Phase 3: Scheduled Maintenance Crawls

- Daily: News and announcements
- Weekly: Critical content (catalogs, admissions, financial aid)
- Monthly: Standard content updates
- Quarterly: Full refresh

---

## Special Considerations

### Authentication Requirements

- **Canvas**: Requires student/faculty login - cannot scrape directly
  - Alternative: Scrape Canvas help pages and login instructions
- **myNKU Portal**: Login-protected
  - Alternative: Scrape portal overview and access instructions
- **Inside NKU**: May have protected sections
  - Strategy: Capture all publicly accessible content

### Sitemap Usage

For more efficient crawling, use sitemap.xml files:

- `https://www.nku.edu/sitemap.xml`
- `https://inside.nku.edu/sitemap.xml`
- `https://catalog.nku.edu/sitemap.xml`

### Robots.txt Compliance

Always respect robots.txt:

```bash
# Check before crawling
curl https://www.nku.edu/robots.txt
```

---

## Data Quality Metrics

Track these metrics for each scraping run:

- **Pages Scraped**: Total number of pages processed
- **Sections Extracted**: Total sections with anchor links
- **Domains Covered**: Number of different subdomains reached
- **Persona Distribution**: Breakdown by persona tag
- **FAQ Coverage**: Number of FAQ-category pages found
- **Failed Pages**: Pages that couldn't be scraped
- **Duplicate Content**: Pages filtered due to duplication

### Success Criteria

A successful comprehensive scrape should yield:

- 2000+ pages from www.nku.edu
- 1000+ pages from inside.nku.edu
- 500+ pages from catalog domains
- 300+ KB articles
- 200+ news articles
- **Total**: 4000+ unique pages with rich metadata

---

## Running Comprehensive Scrapes

### Single Broad Crawl

```bash
cd 01_crawling
python scraper.py
```

### Domain-Specific Crawls

Update `START_URL` in scraper.py for each domain:

```python
# For Inside NKU
START_URL = "https://inside.nku.edu"

# For Catalogs
START_URL = "https://catalog.nku.edu"

# For KB
START_URL = "https://kb.nku.edu"
```

### Monitoring Progress

```bash
# Watch the crawl in real-time
python scraper.py

# Check progress
wc -l campus_data.jsonl  # Linux/Mac
(Get-Content campus_data.jsonl).Count  # PowerShell
```

---

## Next Steps

1. **Run Initial Comprehensive Scrape**: Execute with increased MAX_PAGES
2. **Validate Coverage**: Check that all key domains are represented
3. **Set Up Scheduled Re-scraping**: Use cron/Task Scheduler for regular updates
4. **Monitor Data Quality**: Track metrics and adjust as needed
5. **Integrate with RAG**: Ensure vector store ingests all new data

---

**Note**: This scraping strategy ensures comprehensive coverage of Northern Kentucky University's digital ecosystem, providing the Campus GPT system with accurate, up-to-date information across all student-facing and internal resources.
