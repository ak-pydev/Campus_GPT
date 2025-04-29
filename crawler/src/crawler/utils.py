# utils.py

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

PRIORITY_KEYWORDS = ["about", "faculty", "academics", "program", "admission", "degree", "research", "department"]

def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

def extract_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for tag in soup.find_all("a", href=True):
        href = tag['href'].strip()
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base_url, href).split("#")[0].rstrip("/")
        links.add(normalize_url(absolute))
    return links

def prioritize_links(links):
    priority = []
    normal = []
    for link in links:
        if any(keyword in link.lower() for keyword in PRIORITY_KEYWORDS):
            priority.append(link)
        else:
            normal.append(link)
    return priority + normal

def extract_main_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for remove_tag in soup(["script", "style", "nav", "footer", "header"]):
        remove_tag.extract()
    article = soup.find("article")
    if article:
        return article.get_text(separator=" ", strip=True)
    main = soup.find("main")
    if main:
        return main.get_text(separator=" ", strip=True)
    sections = soup.find_all("section")
    if sections:
        return "\n\n".join(section.get_text(separator=" ", strip=True) for section in sections)
    body = soup.find("body")
    if body:
        return body.get_text(separator=" ", strip=True)
    return soup.get_text(separator=" ", strip=True)
