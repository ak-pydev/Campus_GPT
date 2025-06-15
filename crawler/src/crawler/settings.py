import os

BOT_NAME = "nku_crawler"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# Respect robots.txt
ROBOTSTXT_OBEY = True

# Concurrency & throttling
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 4

# HTTP caching (speeds up development)
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = "httpcache"
COMPRESSION_ENABLED = True

# Retry on server errors
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408]
DOWNLOAD_TIMEOUT = 15



# Identify yourself responsibly
USER_AGENT = "nku_crawler (+https://www.nku.edu/)"

# Disable cookies & telnet console
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
