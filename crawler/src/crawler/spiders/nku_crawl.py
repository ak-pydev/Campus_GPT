# crawler/spiders/nku_crawl.py

import io
import re
import json
import pickle
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

import scrapy
from scrapy import signals
from scrapy.spiders import Spider
from scrapy.linkextractors import LinkExtractor
from pypdf import PdfReader
from docx import Document as DocxDocument

# ─── Keywords for scoping ─────────────────────────────────────────────────────
STUDENT_KEYWORDS = [
    "about", "admissions", "application", "orientation", "undergraduate",
    "campus", "visit", "life", "housing", "catalogue", "departments",
    "tuition", "scholarships", "financial_aid", "aid", "faculty", "academics",
    "programs", "clubs", "advising", "student_services", "resources",
    "calendar", "events", "careers", "research"
]

class NkuInfoSpider(Spider):
    name            = "nku_info"
    allowed_domains = ["nku.edu"]
    start_urls      = ["https://www.nku.edu/"]
    
    # Checkpoint and recovery settings
    checkpoint_file = Path("crawler_checkpoint.pkl")
    visited_urls_file = Path("visited_urls.json")
    max_pages = 5000  # Limit to prevent infinite crawling
    save_checkpoint_every = 100  # Save state every N pages

    # only skip truly irrelevant extensions
    deny_exts = [
        "css", "js", "jpg", "jpeg", "png", "gif", "svg", "ico",
        "xlsx", "xls", "ppt", "pptx", "mp4", "zip"
    ]
    extractor = LinkExtractor(
        allow_domains=allowed_domains,
        deny_extensions=deny_exts,
        # More flexible regex - allows keywords anywhere in path
        allow=[r".*/(" + "|".join(STUDENT_KEYWORDS) + r")(/.*)?$"]
    )

    custom_settings = {
        # ─── Throttling & politeness ────────────────────────────────────────────
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,

        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.5,

        # ─── Memory & logging ──────────────────────────────────────────────────
        "LOG_LEVEL": "INFO",
        "MEMUSAGE_ENABLED": True,
        "MEMUSAGE_LIMIT_MB": 300,
        "MEMUSAGE_CHECK_INTERVAL_SECONDS": 15,

        # ─── Cookies & retries ────────────────────────────────────────────────
        "COOKIES_ENABLED": False,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages_scraped = 0
        self.visited_urls = set()
        self.failed_urls = set()
        self.session_start = datetime.now()
        
        # Load checkpoint if exists
        self.load_checkpoint()
        
        # Memory management
        self.memory_check_interval = 50

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def load_checkpoint(self):
        """Load previous crawl state if checkpoint exists."""
        try:
            if self.checkpoint_file.exists():
                with open(self.checkpoint_file, 'rb') as f:
                    checkpoint = pickle.load(f)
                    self.pages_scraped = checkpoint.get('pages_scraped', 0)
                    self.visited_urls = set(checkpoint.get('visited_urls', []))
                    self.failed_urls = set(checkpoint.get('failed_urls', []))
                    self.logger.info(f"🔄 Loaded checkpoint: {self.pages_scraped} pages scraped, {len(self.visited_urls)} URLs visited")
            
            if self.visited_urls_file.exists():
                with open(self.visited_urls_file, 'r') as f:
                    data = json.load(f)
                    self.visited_urls.update(data.get('visited', []))
                    self.failed_urls.update(data.get('failed', []))
        except Exception as e:
            self.logger.warning(f"Could not load checkpoint: {e}")

    def save_checkpoint(self, force=False):
        """Save current crawl state to checkpoint files."""
        try:
            if force or self.pages_scraped % self.save_checkpoint_every == 0:
                # Save binary checkpoint
                checkpoint = {
                    'pages_scraped': self.pages_scraped,
                    'visited_urls': list(self.visited_urls),
                    'failed_urls': list(self.failed_urls),
                    'timestamp': datetime.now().isoformat()
                }
                
                with open(self.checkpoint_file, 'wb') as f:
                    pickle.dump(checkpoint, f)
                
                # Save JSON for human readability
                with open(self.visited_urls_file, 'w') as f:
                    json.dump({
                        'visited': list(self.visited_urls),
                        'failed': list(self.failed_urls),
                        'pages_scraped': self.pages_scraped,
                        'last_updated': datetime.now().isoformat()
                    }, f, indent=2)
                
                self.logger.info(f"💾 Checkpoint saved: {self.pages_scraped} pages, {len(self.visited_urls)} URLs")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")

    def check_limits_and_memory(self, url):
        """Check if we should continue crawling based on limits and memory."""
        # Check page limit
        if self.pages_scraped >= self.max_pages:
            self.logger.info(f"🛑 Reached maximum page limit ({self.max_pages}). Stopping.")
            return False
        
        # Check if URL already visited
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self.visited_urls:
            return False
        
        # Add to visited set
        self.visited_urls.add(url_hash)
        
        # Periodic memory check
        if self.pages_scraped % self.memory_check_interval == 0:
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                if memory_mb > 400:  # If using more than 400MB
                    self.logger.warning(f"⚠️ High memory usage: {memory_mb:.1f}MB")
            except ImportError:
                pass  # psutil not available
        
        return True

    def parse(self, response):
        url        = response.url
        path       = urlparse(url).path
        suffix     = Path(path).suffix.lower()
        
        # Check limits before processing
        if not self.check_limits_and_memory(url):
            return

        # 1) PDF/DOC/DOCX
        if suffix in {".pdf", ".doc", ".docx"}:
            yield from self.parse_file(response)
            return

        # 2) Only HTML pages
        ctype = response.headers.get(b"Content-Type", b"").decode("utf-8", errors="ignore")
        if "text/html" not in ctype:
            return

        # 3) Scope by keyword in URL path
        lowpath = path.lower()
        if any(kw in lowpath for kw in STUDENT_KEYWORDS):
            # extract headings, paragraphs, list items
            title = response.xpath("//title/text()").get(default="").strip()
            paras = response.css("h1::text, h2::text, h3::text, p::text, li::text").getall()
            text  = " ".join(p.strip() for p in paras if p.strip())
            text  = re.sub(r"\s+", " ", text).strip()

            if text:
                self.pages_scraped += 1
                # Save checkpoint periodically
                self.save_checkpoint()
                
                yield {
                    "type":  "html",
                    "url":    url,
                    "title":  title,
                    "text":   text,
                }

        # 4) Follow any in-scope links
        for link in self.extractor.extract_links(response):
            yield response.follow(link.url, callback=self.parse, errback=self.errback)

    def parse_file(self, response):
        url    = response.url
        suffix = Path(urlparse(url).path).suffix.lower()
        data   = response.body
        text   = ""

        try:
            if suffix == ".pdf":
                reader = PdfReader(io.BytesIO(data))
                text   = "\n".join(p.extract_text() or "" for p in reader.pages)
            elif suffix in {".doc", ".docx"}:
                doc    = DocxDocument(io.BytesIO(data))
                text   = "\n".join(p.text for p in doc.paragraphs if p.text)
            else:
                self.logger.warning(f"Unsupported file type: {suffix} for {url}")
                return

            text = re.sub(r"\s+", " ", text).strip()
            if text and len(text) > 50:  # Only process substantial content
                self.pages_scraped += 1
                # Save checkpoint periodically
                self.save_checkpoint()
                
                yield {
                    "type": "file",
                    "url":  url,
                    "title": Path(urlparse(url).path).name,  # Add title for consistency
                    "text": text,
                }
            else:
                self.logger.debug(f"Skipping file with insufficient content: {url}")
        except Exception as e:
            self.logger.error(f"Error processing file {url}: {str(e)}")

    def spider_closed(self, spider):
        # Final checkpoint save
        self.save_checkpoint(force=True)
        
        elapsed = datetime.now() - self.session_start
        self.logger.info(f"🔖 Crawl finished. Total pages scraped: {self.pages_scraped}")
        self.logger.info(f"⏱️ Session duration: {elapsed}")
        self.logger.info(f"📊 URLs visited: {len(self.visited_urls)}")
        self.logger.info(f"❌ Failed URLs: {len(self.failed_urls)}")

    def errback(self, failure):
        url = failure.request.url
        self.failed_urls.add(hashlib.md5(url.encode()).hexdigest())
        self.logger.warning(f"Request failed: {url} — {failure.value}")
        
        # Save failed URLs periodically
        if len(self.failed_urls) % 10 == 0:
            self.save_checkpoint()
