import re
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.spiders import Spider
from scrapy.linkextractors import LinkExtractor
from bs4 import BeautifulSoup

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

    deny_exts = [
        "css", "js", "jpg", "jpeg", "png", "gif", "svg", "ico",
        "xlsx", "xls", "ppt", "pptx", "mp4", "zip"
    ]
    extractor = LinkExtractor(
        allow_domains=allowed_domains,
        deny_extensions=deny_exts,
        allow=[r"/(" + "|".join(STUDENT_KEYWORDS) + r")(/|$)"]
    )

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        # no ITEM_PIPELINES here
    }

    def parse(self, response):
        url = response.url
        ext = Path(urlparse(url).path).suffix.lower()

        # 1) PDF / DOC / DOCX → hand off
        if ext in {".pdf", ".doc", ".docx"}:
            yield response.request.replace(callback=self.parse_file, dont_filter=True)
            return

        # 2) Skip non-HTML
        content_type = response.headers.get(b"Content-Type", b"").decode(errors="ignore")
        if "text/html" not in content_type:
            return

        # 3) Only student-relevant pages
        path = urlparse(url).path.lower()
        if any(kw in path for kw in STUDENT_KEYWORDS):
            raw = response.text
            text = self.clean_html(raw)
            if text:
                yield {
                    "type":  "html",
                    "url":   url,
                    "title": response.xpath("//title/text()").get(default="").strip(),
                    "text":  text,
                }

        # 4) Follow more links
        for link in self.extractor.extract_links(response):
            yield scrapy.Request(
                link.url, callback=self.parse, errback=self.errback, dont_filter=True
            )

    def parse_file(self, response):
        # (Optionally you could extract PDF/DOC text here or leave to your pipeline)
        yield {
            "type": response.url.split('.')[-1],
            "url":  response.url,
            "body": response.body,
        }

    def clean_html(self, html: str) -> str:
        """Strip tags, remove scripts/styles/navigation, collapse whitespace."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        # collapse whitespace and lower-case
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def errback(self, failure):
        self.logger.warning(f"Request failed: {failure.request.url} — {failure.value}")
