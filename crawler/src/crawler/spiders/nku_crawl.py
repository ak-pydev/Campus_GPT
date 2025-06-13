import re
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.spiders import Spider
from scrapy.linkextractors import LinkExtractor
from scrapy.exceptions import CloseSpider
from twisted.internet import threads

STUDENT_KEYWORDS = [
    "about", "admissions", "faq", "undergraduate",
    "campus", "visit", "life", "departments", "tuition","housing","catalogue","faculty","academics"
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
        # make sure we only store HTML
        "MEDIA_ALLOW_REDIRECTS": False,
    }

    def parse(self, response):
        # skip non-HTML
        content_type = response.headers.get(b"Content-Type", b"").decode()
        if "text/html" not in content_type:
            return

        url_path = urlparse(response.url).path.lower()
        # only pages that look “student-friendly”
        if any(kw in url_path for kw in STUDENT_KEYWORDS):
            yield {
                "url": response.url,
                "title": response.xpath("//title/text()").get(default="").strip(),
                "html": response.text,
            }

        # follow only links that contain our keywords (else skip PDFs, deep APIs, etc.)
        extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=["pdf", "doc", "docx", "ppt", "pptx", "jpg", "css", "js", "svg"],
            allow=[r"/(" + "|".join(STUDENT_KEYWORDS) + r")/"]
        )
        for link in extractor.extract_links(response):
            yield scrapy.Request(
                link.url,
                callback=self.parse,
                errback=self.errback,
                dont_filter=True
            )

    def errback(self, failure):
        self.logger.warning(f"Request failed: {failure.request.url} — {failure.value}")

