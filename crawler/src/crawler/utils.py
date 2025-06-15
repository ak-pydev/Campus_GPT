# utils.py

import re
import aiohttp
import asyncio
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from urllib.parse import urljoin, urlparse
from pathlib import Path
from xml.etree import ElementTree

# suppress XML warnings if using BeautifulSoup for XML
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# keywords for prioritizing academic/relevant pages
PRIORITY_KEYWORDS = [
    "about", "faculty", "academics", "program",
    "admission", "degree", "research", "department","isss"
]

# file-type mapping for bucketed downloads
FILE_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
}


def normalize_url(url: str) -> str:
    """
    Strip query strings, fragments, and trailing slashes.
    Ensures consistency for de-duping.
    """
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return normalized.rstrip("/")


async def parse_sitemap(url: str) -> list[str]:
    """
    Download an XML sitemap (or sitemap index) and return a list of all <loc> URLs.
    Works with both standard sitemaps and sitemap index files.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                resp.raise_for_status()
                xml_content = await resp.text()
    except Exception:
        return []
    try:
        root = ElementTree.fromstring(xml_content)
        # namespace-agnostic search for <loc> tags
        return [
            normalize_url(loc.text)
            for loc in root.findall(".//loc")
            if loc.text
        ]
    except ElementTree.ParseError:
        # fallback: use BeautifulSoup XML parser if ET fails
        soup = BeautifulSoup(xml_content, "xml")
        return [
            normalize_url(tag.get_text())
            for tag in soup.find_all("loc")
            if tag.string
        ]


def extract_links(
    html: str,
    base_url: str,
    whitelist: list[str] | None = None
) -> set[str]:
    """
    Parse <a href> links, resolve relative URLs, normalize,
    and optionally filter by a domain whitelist.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith(("mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        absolute = normalize_url(absolute)
        if whitelist:
            netloc = urlparse(absolute).netloc.lower()
            if not any(d.lower() in netloc for d in whitelist):
                continue
        links.add(absolute)
    return links


def prioritize_links(links: list[str] | set[str]) -> list[str]:
    """
    Return URLs containing priority keywords first, then the rest.
    """
    priority, normal = [], []
    for link in links:
        if any(kw in link.lower() for kw in PRIORITY_KEYWORDS):
            priority.append(link)
        else:
            normal.append(link)
    return priority + normal


def extract_main_text_from_html(html: str) -> str:
    """
    Strip scripts, styles, nav, header, footer, then extract from
    <article>, <main>, <section>, or fallback to <body> or full text.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    if article := soup.find("article"):
        return article.get_text(separator=" ", strip=True)
    if main := soup.find("main"):
        return main.get_text(separator=" ", strip=True)
    sections = soup.find_all("section")
    if sections:
        return "\n\n".join(sec.get_text(separator=" ", strip=True)
                           for sec in sections)
    if body := soup.find("body"):
        return body.get_text(separator=" ", strip=True)
    return soup.get_text(separator=" ", strip=True)


def get_file_type(url: str) -> str | None:
    """
    Return one of 'pdf', 'docx', 'pptx', 'xlsx' if URL ends with
    a matching extension, else None.
    """
    ext = Path(urlparse(url).path).suffix.lower()
    return FILE_EXTENSIONS.get(ext)
