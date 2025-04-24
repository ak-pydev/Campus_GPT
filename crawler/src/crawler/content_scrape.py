import asyncio
import aiofiles
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urlparse
import json
import random
import re
import logging
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import warnings

# Suppress XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("content_collector.log"),
        logging.StreamHandler()
    ]
)

class SiteContentCollector:
    def __init__(self, sitemap_file="site_map.json", statuses_file="link_statuses.json", output_dir="pages_text"):
        self.sitemap_file = sitemap_file
        self.statuses_file = statuses_file
        self.output_dir = Path(output_dir)
        self.text_dir = self.output_dir / "text"
        self.image_dir = self.output_dir / "thumbnails"
        self.meta_dir = self.output_dir / "meta"
        self.visited = []
        self.failed_urls = []
        self.status_codes = {}
        self.user_agent = self.get_random_user_agent()
        self.playwright = None
        self.browser = None
        self.context = None

    def get_random_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    def load_data(self):
        with open(self.statuses_file) as f:
            self.status_codes = json.load(f)
        self.visited = [url for url, status in self.status_codes.items() if status == 200]

    def slugify(self, url):
        path = urlparse(url).path.strip("/") or "home"
        return re.sub(r"[^\w\-]", "_", path)

    async def fetch_and_extract(self, url):
        try:
            page = await self.context.new_page()
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeoutError:
                self.failed_urls.append(url)
                logging.warning(f"Timeout while loading: {url}")
                return

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            title = soup.title.string.strip() if soup.title else ""

            main = soup.find("main") or soup.find("article") or soup.body
            text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)

            slug = self.slugify(url)

            text_path = self.text_dir / f"{slug}.txt"
            async with aiofiles.open(text_path, "w", encoding="utf-8") as f:
                await f.write(f"URL: {url}\nTitle: {title}\n\n{text}")

            image_path = self.image_dir / f"{slug}.png"
            await page.screenshot(path=str(image_path))

            meta = {
                "url": url,
                "title": title,
                "text_file": str(text_path.name),
                "screenshot": str(image_path.name)
            }
            meta_path = self.meta_dir / f"{slug}_meta.json"
            async with aiofiles.open(meta_path, "w", encoding="utf-8") as mf:
                await mf.write(json.dumps(meta, indent=2))

            logging.info(f"Saved: {url} → {text_path.name}, thumbnail: {image_path.name}")
        except Exception as e:
            self.failed_urls.append(url)
            logging.error(f"Failed to process {url}: {e}")

    async def run(self):
        self.load_data()
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(user_agent=self.user_agent)

        for url in self.visited:
            await self.fetch_and_extract(url)

        await self.browser.close()
        await self.playwright.stop()

        if self.failed_urls:
            async with aiofiles.open("failed_urls.json", "w", encoding="utf-8") as f:
                await f.write(json.dumps(self.failed_urls, indent=2))
            logging.info("Saved failed URLs to failed_urls.json")

if __name__ == "__main__":
    collector = SiteContentCollector(
        sitemap_file="site_map.json",
        statuses_file="link_statuses.json",
        output_dir="pages_text"
    )
    asyncio.run(collector.run())
