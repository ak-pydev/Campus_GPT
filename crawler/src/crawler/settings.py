# settings.py

BOT_NAME = "nku_crawler"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# ─── Crawl rate ────────────────────────────────────────────────────────────────
ROBOTSTXT_OBEY                = True
DOWNLOAD_DELAY                = 1.0
CONCURRENT_REQUESTS           = 4
CONCURRENT_REQUESTS_PER_DOMAIN= 1

# ─── AutoThrottle ──────────────────────────────────────────────────────────────
AUTOTHROTTLE_ENABLED          = True
AUTOTHROTTLE_START_DELAY      = 1.0
AUTOTHROTTLE_MAX_DELAY        = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY=0.5

# ─── Disable HTTP cache (saves memory) ────────────────────────────────────────
HTTPCACHE_ENABLED             = False

# ─── Pipelines & Feed Export ──────────────────────────────────────────────────
ITEM_PIPELINES = {
    "crawler.pipelines.TextFilePipeline": 300,
}
# (Optional) also output JSONL as a backup, streamed to disk
FEEDS = {
    "crawl_meta.json": {
        "format":    "jsonlines",
        "encoding":  "utf8",
        "overwrite": True,
    }
}

# ─── Memory monitoring & crash prevention ──────────────────────────────────────
MEMUSAGE_ENABLED              = True
MEMUSAGE_LIMIT_MB             = 500    # Increased limit to 500 MB
MEMUSAGE_CHECK_INTERVAL_SECONDS=10     # Check more frequently
MEMUSAGE_WARNING_MB           = 400    # Warn at 400 MB

# ─── Duplication filter settings ──────────────────────────────────────────────
DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'
DUPEFILTER_DEBUG = True

# ─── Request timeout settings ─────────────────────────────────────────────────
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_DELAY_RANDOMIZE = True

# ─── Retries, Logging, Cookies ────────────────────────────────────────────────
RETRY_ENABLED                 = True
RETRY_TIMES                   = 2     # Increased retry attempts
RETRY_HTTP_CODES              = [500, 502, 503, 504, 408, 429]
LOG_LEVEL                     = "INFO"
COOKIES_ENABLED               = False
TELNETCONSOLE_ENABLED         = False

# ─── Additional crash prevention ──────────────────────────────────────────────
RANDOMIZE_DOWNLOAD_DELAY      = True
DNSCACHE_ENABLED              = True
DNSCACHE_SIZE                 = 10000
DNS_TIMEOUT                   = 60
