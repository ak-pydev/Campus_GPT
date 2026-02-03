"""
Enhanced Web Scraper for Campus GPT
====================================

Features:
- Markdown-first scraping with crawl4ai
- Header anchor extraction for deep linking
- Section-level chunking
- Persona tagging (student, faculty, prospective, etc.)
- FAQ quick link integration
- Multi-domain support (nku.edu, inside.nku.edu, catalog.nku.edu, etc.)
"""

import asyncio
import json
import random
import re
from collections import deque
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

# Configuration
START_URL = "https://www.nku.edu"
MAX_PAGES = 5000  # Comprehensive scraping for 4000+ pages
OUTPUT_FILE = "campus_data.jsonl"

# Allowed Domains - Comprehensive NKU Web Presence
ALLOWED_DOMAINS = [
    "nku.edu",                    # Main public site
    "www.nku.edu",                # Main public site (www)
    "inside.nku.edu",             # Internal resources & departmental info
    "catalog.nku.edu",            # Academic catalogs
    "undergrad.catalog.nku.edu",  # Undergraduate catalog
    "graduate.catalog.nku.edu",   # Graduate catalog
    "mynku.nku.edu",              # Student portal (if accessible)
    "kb.nku.edu",                 # IT Service Desk Knowledge Base
    "news.nku.edu",               # Campus news
]

# Ignored Extensions
# Note: PDFs are handled separately by pdf_scraper.py for deep-linking and layout-aware extraction
IGNORED_EXTENSIONS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mov', 
    '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.zip', '.rar', 
    '.exe', '.css', '.js', '.xml', '.json'
)

# User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

# Persona Detection Patterns
PERSONA_PATTERNS = {
    "prospective": ["admissions", "apply", "visit", "future-students", "undergraduate-admissions"],
    "student": ["current-students", "registrar", "myportal", "canvas", "student-life"],
    "faculty": ["faculty", "staff", "inside.nku.edu", "faculty-resources"],
    "financial": ["tuition", "financial-aid", "bursar", "scholarships", "cost"],
    "housing": ["housing", "residence", "dorms", "living-on-campus"],
}

# FAQ Quick Links - High-Traffic Questions
FAQ_LINKS = {
    "campus_map": {
        "url": "https://www.nku.edu/map",
        "title": "NKU Campus Map",
        "keywords": ["map", "campus map", "where is", "location", "building", "directions"],
        "description": "Interactive campus map showing all buildings, parking, and facilities."
    },
    "mynku_portal": {
        "url": "https://www.nku.edu/mynku",
        "title": "MyNKU Student Portal",
        "keywords": ["mynku", "portal", "login", "canvas", "student portal", "blackboard"],
        "description": "Access your student portal for grades, registration, and course materials."
    },
    "financial_aid": {
        "url": "https://www.nku.edu/financialaid",
        "title": "Financial Aid & Tuition",
        "keywords": ["tuition", "financial aid", "scholarships", "cost", "fafsa", "payment"],
        "description": "Information about tuition costs, financial aid, and scholarship opportunities."
    },
    "registrar": {
        "url": "https://www.nku.edu/registrar",
        "title": "Registrar's Office",
        "keywords": ["registration", "transcript", "records", "enroll", "add drop", "schedule"],
        "description": "Registration, transcripts, academic records, and enrollment services."
    },
    "academic_calendar": {
        "url": "https://www.nku.edu/academics/calendar",
        "title": "Academic Calendar",
        "keywords": ["calendar", "deadlines", "academic calendar", "semester dates", "finals"],
        "description": "Important academic dates, deadlines, and semester schedules."
    }
}


def is_valid_url(url):
    """Check if URL is valid for crawling."""
    parsed = urlparse(url)
    
    # Check domain
    if not any(domain in parsed.netloc for domain in ALLOWED_DOMAINS):
        return False
    
    # Check extension
    if parsed.path.lower().endswith(IGNORED_EXTENSIONS):
        return False
    
    # Skip fragments (same page)
    if '#' in url:
        return False
        
    return True


def clean_text(text):
    """Remove boilerplate, noise, and duplicate content."""
    if not text:
        return ""

    # Boilerplate patterns to remove
    boilerplate_patterns = [
        r"NKU uses cookies on this website.*",
        r"This website uses cookies!.*?Accept",
        r"\[!\[Canvas online learning\].*?Search the NKU Site",
        r"\* \[Prospective Students\].*",
        r"Northern Kentucky University\s+Nunn Drive \| Highland Heights, Kentucky 41099\s+Phone: \(859\) 572-5100",
        r"© \d{4} Northern Kentucky University. All rights reserved.",
        r"Connect with us on social media:",
        r"\[Skip to main content\]\(.*?\)",
        r"Toggle navigation",
        r"Enter the search term or name",
        r"↑\s+top",
        r"\[QUICK LINKS\]\(.*?\)",
        r"Loading - JavaScript",
    ]
    
    cleaned = text
    for pattern in boilerplate_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)

    # Remove sequential duplicate lines
    lines = cleaned.splitlines()
    unique_lines = []
    prev_line = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped != prev_line:
            unique_lines.append(line)
        prev_line = stripped

    return "\n".join(unique_lines).strip()


def extract_header_anchors(html_content, base_url):
    """
    Extract header anchors (h1-h6 with id attributes) for deep linking.
    Returns a list of {anchor_id, header_text, anchor_url, level}.
    """
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    anchors = []
    
    # Find all headers (h1-h6) with id attributes
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        anchor_id = header.get('id')
        if anchor_id:
            anchors.append({
                'anchor_id': anchor_id,
                'header_text': header.get_text(strip=True),
                'anchor_url': f"{base_url}#{anchor_id}",
                'level': header.name  # h1, h2, etc.
            })
    
    return anchors


def detect_persona(url):
    """Detect target persona based on URL patterns."""
    url_lower = url.lower()
    for persona, patterns in PERSONA_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return persona
    return "all"


def create_section_chunks(markdown_content, anchors, base_url):
    """
    Split markdown content into sections based on headers and their anchors.
    Each chunk includes the section content and metadata for deep linking.
    """
    if not markdown_content:
        return []
    
    chunks = []
    lines = markdown_content.split('\n')
    
    # If we have anchors, create section-based chunks
    if anchors:
        current_section = {
            'header': None,
            'anchor_id': None,
            'anchor_url': base_url,
            'level': None,
            'content': []
        }
        
        for line in lines:
            # Check if this line is a markdown header
            header_match = re.match(r'^(#{1,6})\s+(.+)', line)
            
            if header_match:
                # Save previous section if it has content
                if current_section['content']:
                    section_text = '\n'.join(current_section['content']).strip()
                    if len(section_text) > 50:  # Minimum content length
                        chunks.append({
                            'section_header': current_section['header'],
                            'section_content': section_text,
                            'anchor_id': current_section['anchor_id'],
                            'anchor_url': current_section['anchor_url'],
                            'header_level': current_section['level']
                        })
                
                # Start new section
                header_level = len(header_match.group(1))
                header_text = header_match.group(2).strip()
                
                # Find matching anchor
                matching_anchor = None
                for anchor in anchors:
                    if anchor['header_text'] == header_text:
                        matching_anchor = anchor
                        break
                
                current_section = {
                    'header': header_text,
                    'anchor_id': matching_anchor['anchor_id'] if matching_anchor else None,
                    'anchor_url': matching_anchor['anchor_url'] if matching_anchor else base_url,
                    'level': f"h{header_level}",
                    'content': [line]
                }
            else:
                current_section['content'].append(line)
        
        # Don't forget the last section
        if current_section['content']:
            section_text = '\n'.join(current_section['content']).strip()
            if len(section_text) > 50:
                chunks.append({
                    'section_header': current_section['header'],
                    'section_content': section_text,
                    'anchor_id': current_section['anchor_id'],
                    'anchor_url': current_section['anchor_url'],
                    'header_level': current_section['level']
                })
    
    # If no chunks created (no anchors or no sections), return the whole content
    if not chunks:
        chunks.append({
            'section_header': None,
            'section_content': markdown_content,
            'anchor_id': None,
            'anchor_url': base_url,
            'header_level': None
        })
    
    return chunks


async def main():
    # Setup queue and visited set
    queue = deque([START_URL])
    visited = set([START_URL])
    pages_crawled = 0
    sections_saved = 0

    # Clear output file or create new
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        pass

    async with AsyncWebCrawler(verbose=True) as crawler:
        while queue and pages_crawled < MAX_PAGES:
            current_url = queue.popleft()
            print(f"[*] ({pages_crawled + 1}/{MAX_PAGES}) Scraping: {current_url}...")

            # Ethics: Random delay (1-3 seconds)
            await asyncio.sleep(random.uniform(1, 3))
            user_agent = random.choice(USER_AGENTS)

            try:
                result = await crawler.arun(
                    url=current_url,
                    user_agent=user_agent
                )

                if result.success:
                    pages_crawled += 1
                    
                    # 1. Get Raw Markdown Content
                    raw_content = result.markdown
                    clean_content = clean_text(raw_content)
                    
                    if len(clean_content) > 100:  # Filter out pages that are empty after cleaning
                        # 2. Extract Header Anchors for Deep Linking
                        anchors = extract_header_anchors(result.html, current_url)
                        
                        # 3. Detect Persona for Targeted Responses
                        persona = detect_persona(current_url)
                        
                        # 4. Create Section-Based Chunks (with anchor links)
                        section_chunks = create_section_chunks(clean_content, anchors, current_url)
                        
                        # 5. Check if this URL matches any FAQ quick links
                        faq_category = None
                        for category, faq_info in FAQ_LINKS.items():
                            if faq_info["url"] in current_url:
                                faq_category = category
                                break
                        
                        # 6. Save Each Section as a Separate Entry
                        page_title = result.metadata.get("title", "No Title")
                        
                        for idx, chunk in enumerate(section_chunks):
                            # Prepare metadata-rich data entry
                            data = {
                                # Core Content
                                "title": page_title,
                                "section_header": chunk.get("section_header"),
                                "text": chunk.get("section_content"),
                                
                                # Deep Linking Metadata
                                "url": current_url,
                                "anchor_url": chunk.get("anchor_url"),  # URL with #anchor
                                "anchor_id": chunk.get("anchor_id"),
                                "header_level": chunk.get("header_level"),
                                
                                # Persona & FAQ Tagging
                                "persona": persona,
                                "faq_category": faq_category,
                                
                                # Additional Metadata
                                "chunk_index": idx,
                                "total_chunks": len(section_chunks),
                                "page_scraped_at": result.metadata.get("scraped_at", ""),
                            }
                            
                            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                                f.write(json.dumps(data) + "\n")
                            
                            sections_saved += 1
                        
                        print(f"    -> Saved {len(section_chunks)} sections with {len(anchors)} anchors (persona: {persona}).")
                    else:
                        print(f"    -> Skipped (content too short after cleaning).")

                    # 7. Extract Links for Recursion
                    if result.html:
                        soup = BeautifulSoup(result.html, 'html.parser')
                        for link in soup.find_all('a', href=True):
                            absolute_url = urljoin(current_url, link['href'])
                            
                            # Normalize: remove fragments
                            if '#' in absolute_url:
                                absolute_url = absolute_url.split('#')[0]

                            # Add to queue if valid and not visited
                            if (absolute_url not in visited and 
                                is_valid_url(absolute_url)):
                                visited.add(absolute_url)
                                queue.append(absolute_url)

                else:
                    print(f"[!] Failed to scrape {current_url}: {result.error_message}")

            except Exception as e:
                print(f"[!] Error processing {current_url}: {str(e)}")

    print(f"\n[+] Crawl complete. {pages_crawled} pages scraped, {sections_saved} sections saved to {OUTPUT_FILE}")
    print(f"[+] Each section includes anchor URLs for deep linking and persona tags for targeted responses.")


if __name__ == "__main__":
    asyncio.run(main())
