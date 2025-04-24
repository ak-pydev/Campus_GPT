import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import tldextract
from urllib.robotparser import RobotFileParser
import json
import xml.etree.ElementTree as ET
import random
import logging
import os
from pathlib import Path
from playwright.async_api import async_playwright

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)

class AsyncSiteCrawler:
    def __init__(self, start_url, max_pages=10000, concurrency=10, user_agent=None, allowed_path=None):
        self.start_url = start_url.rstrip("/")
        self.domain = tldextract.extract(start_url).top_domain_under_public_suffix
        self.allowed_path = allowed_path or "/"
        self.max_pages = max_pages
        self.visited = set()
        self.to_visit = set([start_url])
        self.site_map = {}
        self.status_codes = {}
        self.suspected_captchas = []
        self.session = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.user_agent = user_agent or self.get_random_user_agent()
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.robot_parser = RobotFileParser()
        self._init_robots()

        # Ensure downloads folder exists
        Path("downloads").mkdir(parents=True, exist_ok=True)

    def get_random_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    def _init_robots(self):
        robots_url = urljoin(self.start_url, "/robots.txt")
        self.robot_parser.set_url(robots_url)
        try:
            self.robot_parser.read()
            logging.info(f"Loaded robots.txt from {robots_url}")
            logging.info(f"Allowed to crawl start URL? {self.robot_parser.can_fetch(self.user_agent, self.start_url)}")
        except:
            logging.warning("Failed to load robots.txt")

    def allowed(self, url):
        parsed = urlparse(url)
        path = parsed.path or "/"
        same_domain = tldextract.extract(parsed.netloc).top_domain_under_public_suffix == self.domain
        path_ok = path.startswith(self.allowed_path)
        robots_ok = self.robot_parser.can_fetch(self.user_agent, url)
        return same_domain and path_ok and robots_ok

    async def fetch(self, url, retries=2):
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.start_url
        }
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    async with self.session.get(url, headers=headers, timeout=15) as response:
                        self.status_codes[url] = response.status
                        content_type = response.headers.get("Content-Type", "")

                        if response.status == 200:
                            if not content_type.startswith("text/html"):
                                filename = Path(urlparse(url).path).name or f"file_{len(self.status_codes)}"
                                path = Path("downloads") / filename
                                async with aiofiles.open(path, "wb") as f:
                                    await f.write(await response.read())
                                logging.info(f"Saved non-HTML content: {url} to {path}")
                                return None

                            html = await response.text()
                            if self.detect_captcha(html):
                                self.suspected_captchas.append(url)
                                logging.warning(f"CAPTCHA detected: {url}")
                                return await self.fetch_with_playwright(url)
                            return html
                        elif response.status in (403, 429, 503):
                            logging.warning(f"Fallback to Playwright for {url} (status: {response.status})")
                            return await self.fetch_with_playwright(url)
                except Exception as e:
                    self.status_codes[url] = str(e)
                    logging.error(f"Fetch failed for {url}: {e}")
                    await asyncio.sleep(2 ** attempt)
        return None

    async def fetch_with_playwright(self, url):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(user_agent=self.user_agent)

        try:
            page = await self.context.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            content = await page.content()
            self.status_codes[url] = 200
            return content
        except Exception as e:
            self.status_codes[url] = str(e)
            logging.error(f"Playwright failed for {url}: {e}")
        return None

    def detect_captcha(self, html):
        return any(x in html.lower() for x in ["captcha", "i'm not a robot", "cloudflare", "js challenge"])

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        links = set()
        for tag in soup.find_all("a", href=True):
            href = tag['href'].strip()
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue
            absolute = urljoin(base_url, href).split("#")[0].rstrip("/")
            links.add(absolute)
        return links

    def build_tree_path(self, url):
        path = urlparse(url).path.strip("/")
        parts = path.split("/") if path else ["home"]
        node = self.site_map
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    async def crawl(self):
        async with aiohttp.ClientSession() as self.session:
            while self.to_visit and len(self.visited) < self.max_pages:
                batch = list(self.to_visit)[:self.concurrency]
                self.to_visit.difference_update(batch)
                tasks = [self.handle_url(url) for url in batch]
                await asyncio.gather(*tasks)

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logging.info(f"\nCrawling completed. Visited: {len(self.visited)} pages")
        logging.info(f"Suspected captchas: {len(self.suspected_captchas)}")
        logging.info(f"Status codes: {len(self.status_codes)}")

    async def handle_url(self, url):
        if url in self.visited or not self.allowed(url):
            return
        logging.info(f"Visiting: {url}")
        html = await self.fetch(url)
        self.visited.add(url)
        if html:
            self.build_tree_path(url)
            links = self.extract_links(html, url)
            for link in links:
                if link not in self.visited and self.allowed(link):
                    self.to_visit.add(link)

    async def save_json(self, filename="site_map.json"):
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(self.site_map, indent=2))

    async def save_xml(self, filename="sitemap.xml"):
        urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for url in sorted(self.visited):
            if self.status_codes.get(url) == 200:
                url_elem = ET.SubElement(urlset, "url")
                loc_elem = ET.SubElement(url_elem, "loc")
                loc_elem.text = url
        tree = ET.ElementTree(urlset)
        tree.write(filename, encoding="utf-8", xml_declaration=True)

    async def save_status_codes(self, filename="link_statuses.json"):
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(self.status_codes, indent=2))

    async def save_suspected_captchas(self, filename="suspected_captchas.json"):
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(self.suspected_captchas, indent=2))


if __name__ == "__main__":
    start_url = "https://www.nku.edu/"
    allowed_path = "/"

    crawler = AsyncSiteCrawler(start_url, max_pages=10000, concurrency=10, allowed_path=allowed_path)

    asyncio.run(crawler.crawl())
    asyncio.run(crawler.save_json("site_map.json"))
    asyncio.run(crawler.save_xml("sitemap.xml"))
    asyncio.run(crawler.save_status_codes("link_statuses.json"))
    asyncio.run(crawler.save_suspected_captchas("suspected_captchas.json"))
    logging.info("Site map, sitemap, link statuses, and suspected captchas saved.")
