import re
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.spiders import Spider
from scrapy.linkextractors import LinkExtractor

# keywords to scope “student-friendly” pages
STUDENT_KEYWORDS = [
    "about", "admissions", "application", "orientation", "undergraduate",
    "campus", "visit", "life", "housing", "catalogue", "departments",
    "tuition", "scholarships", "financial_aid", "aid", "faculty", "academics",
    "programs", "clubs", "advising", "student_services", "resources",
    "calendar", "events", "careers", "research"
]

class NkuInfoSpider(Spider):
    name = "nku_info"
    allowed_domains = ["nku.edu"]
    start_urls = ["https://www.nku.edu/"]
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "ITEM_PIPELINES": {
            "myproject.pipelines.PageTextPipeline": 300,
        },
    }

    def parse(self, response):
        # figure out what type of resource this is
        url = response.url
        ext = Path(urlparse(url).path).suffix.lower()

        # ─── 1) PDF/DOC(DOCX) ─────────────────────────────
        if ext in {".pdf", ".doc", ".docx"}:
            # hand off to parse_file()
            yield scrapy.Request(
                url, callback=self.parse_file, dont_filter=True
            )
            return

        # ─── 2) everything else must be HTML ─────────────
        content_type = response.headers.get(b"Content-Type", b"").decode()
        if "text/html" not in content_type:
            return

        path = urlparse(url).path.lower()
        # only yield pages whose URL path contains one of our keywords
        if any(kw in path for kw in STUDENT_KEYWORDS):
            yield {
                "type": "html",
                "url": url,
                "title": response.xpath("//title/text()").get(default="").strip(),
                "html": response.text,
            }

        # ─── 3) follow further links (HTML, PDF, DOC/DOCX only) ───
        extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=[
                # block everything except html, pdf, doc, docx
                "css", "js", "jpg", "jpeg", "png", "gif", "svg", "ico",
                "xlsx", "xls", "ppt", "pptx", "mp4", "zip"
            ],
            # only follow URLs that contain at least one student keyword
            allow=[r"/(" + "|".join(STUDENT_KEYWORDS) + r")(/|$)"]
        )
        for link in extractor.extract_links(response):
            yield scrapy.Request(link.url, callback=self.parse, errback=self.errback, dont_filter=True)

    def parse_file(self, response):
        """Save PDF/DOC(DOCX) content or pass it downstream for pipeline/download."""
        url = response.url
        ext = Path(urlparse(url).path).suffix.lower().lstrip(".")
        yield {
            "type": ext,
            "url": url,
            "body": response.body,       # raw bytes of PDF or DOCX
        }

    def errback(self, failure):
        self.logger.warning(f"Request failed: {failure.request.url} — {failure.value}")
