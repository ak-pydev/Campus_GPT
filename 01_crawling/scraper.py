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
MAX_PAGES = 1000  # Increased for production run
OUTPUT_FILE = "campus_data.jsonl"
ALLOWED_DOMAINS = ["nku.edu", "www.nku.edu"]
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

def is_valid_url(url):
    """Check if URL is valid for crawling."""
    parsed = urlparse(url)
    
    # Check domain
    if parsed.netloc not in ALLOWED_DOMAINS:
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

    # 1. Remove specific NKU boilerplate phrases
    boilerplate_patterns = [
        # Cookie Consent (Variant 1 - Bottom of page)
        r"NKU uses cookies on this website.*", 
        # Cookie Consent (Variant 2 - Top/Pop-up)
        r"This website uses cookies!.*?Accept",
        
        # Aggressed Header Removal: From Canvas link to Search Site
        # Captures the visual nav links, the mobile menu (* one, * two), and everything in between.
        r"\[!\[Canvas online learning\].*?Search the NKU Site",
        
        # Standard Footer Links Block
        r"\* \[Prospective Students\].*", 
        
        # Original patterns (kept for safety)
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

    # 2. Remove sequential duplicate lines (common in nav menus)
    lines = cleaned.splitlines()
    unique_lines = []
    prev_line = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Simple de-duplication
        if stripped != prev_line:
            unique_lines.append(line)
        prev_line = stripped

    return "\n".join(unique_lines).strip()

async def main():
    # Setup queue and visited set
    queue = deque([START_URL])
    visited = set([START_URL])
    pages_crawled = 0

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
                    # word_count_threshold=10, # Optional: skip very short pages
                    user_agent=user_agent
                )

                if result.success:
                    pages_crawled += 1
                    
                    # 1. Save Data
                    raw_content = result.markdown
                    clean_content = clean_text(raw_content)
                    
                    if len(clean_content) > 100: # Filter out pages that are empty after cleaning
                        data = {
                            "title": result.metadata.get("title", "No Title"),
                            "url": current_url,
                            "text": clean_content
                        }
                        
                        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(data) + "\n")
                        
                        print(f"    -> Saved {len(clean_content)} chars (cleaned).")
                    else:
                        print(f"    -> Skipped (content too short after cleaning).")

                    # 2. Extract Links for Recursion
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

    print(f"\n[+] Crawl complete. {pages_crawled} pages scraped. Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
