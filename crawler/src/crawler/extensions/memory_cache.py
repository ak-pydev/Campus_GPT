# src/crawler/extensions/memory_cache.py
from scrapy.extensions.httpcache.storage import CacheStorage
from scrapy.utils.request import fingerprint as request_fingerprint

class MemoryCacheStorage(CacheStorage):
    """
    A simple in-memory HTTP cache backend.
    """
    def __init__(self, settings):
        super().__init__(settings)
        self._cache = {}

    def open_spider(self, spider):
        self._cache.clear()

    def close_spider(self, spider):
        self._cache.clear()

    def retrieve_response(self, spider, request):
        fp = request_fingerprint(request)
        return self._cache.get(fp)

    def store_response(self, spider, request, response):
        fp = request_fingerprint(request)
        self._cache[fp] = response
