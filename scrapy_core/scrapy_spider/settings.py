BOT_NAME = "scrapy_spider"

SPIDER_MODULES = ["scrapy_spider.spiders"]
NEWSPIDER_MODULE = "scrapy_spider.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "scrapy_spider (+http://www.yourdomain.com)"

# 设置 User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0'

# 不遵守 robots.txt 规则
ROBOTSTXT_OBEY = False

# Concurrency and throttling settings
# 并发请求数量
# 全局并发
CONCURRENT_REQUESTS = 64
# 单域名并发
CONCURRENT_REQUESTS_PER_DOMAIN = 8
# 设置下载延迟，避免过快请求
DOWNLOAD_DELAY = 0.5
# # 随机化下载延迟，避免被封禁(先停用)
# RANDOMIZE_DOWNLOAD_DELAY = True

# 启用自动限速扩展
AUTOTHROTTLE_ENABLED = True
# 初始延迟（秒）
AUTOTHROTTLE_START_DELAY = 2
# 最大允许延迟（秒）
AUTOTHROTTLE_MAX_DELAY = 5

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

# 开启item管道
ITEM_PIPELINES = {
   # JSONL 输出（调试用，可保留）
   'scrapy_spider.pipelines.Hanime1SpiderJsonlPipeline': 300,
   # SQLite 主力存储（数字越大优先级越低，先 JSONL 再 SQLite）
   'scrapy_spider.pipelines.Hanime1SpiderSqlitePipeline': 301,
}

# 降低日志级别，提速
# 仅输出一般信息、警告和错误信息
LOG_LEVEL = 'INFO'
