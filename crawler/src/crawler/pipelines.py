# crawler/pipelines.py

from pathlib import Path

class TextFilePipeline:
    def open_spider(self, spider):
        self.outdir = Path("output/text")
        self.outdir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item, spider):
        # item: { type, url, title?, text }
        # create a filesystem-safe name from the URL path
        path = item["url"].split("://", 1)[-1]
        fname = path.replace("/", "_") or "home"
        filepath = self.outdir / f"{fname}.txt"

        # write plain text
        if item["type"] == "html":
            content = f"{item.get('title','')}\n\n{item['text']}"
        else:
            content = item["text"]

        filepath.write_text(content, encoding="utf8")
        spider.logger.info(f"Saved → {filepath}")
        return item
