import re
import json

import requests
import scrapy
from pathlib import Path

# 导入item类
from scrapy_spider.items import Hanime1SpiderItem

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
    "Referer": "https://hanime1.me",
}

xray_PROXY = "http://127.0.0.1:10909"  # 本地内核的代理地址
v2rayN_PROXY = "http://127.0.0.1:10809"  # v2rayN的代理地址

# ── 分层爬取的页数上限 ──────────────────────────────────
# Tier 1（列表页）默认爬前 3 页，可根据需要调大
MAX_LIST_PAGES = 3


class Hanime1SpiderSpider(scrapy.Spider):
    name = "Hanime1_spider"
    allowed_domains = ["hanime1.me"]
    start_urls = ["https://hanime1.me/search"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                headers=headers,
                callback=self.parse,
                meta={"proxy": xray_PROXY},
            )

    # ── Tier 1：只爬列表页，直接 yield ────────────────────

    def parse(self, response):
        print("Hanime1爬虫正在运行")

        # 当前的页数
        current_page = response.meta.get("page", 1)
        print(f"当前爬取页数：第 {current_page} 页")

        # 当前视频序号索引（连续计数，不依赖固定页大小）
        current_index = response.meta.get("sort_order", 1)

        # 获取视频列表
        video_list = response.xpath('//div[@class="horizontal-row"]/div')

        for video in video_list:
            item = Hanime1SpiderItem()

            video_link = video.xpath('.//a[@class="video-link"]/@href').get('')

            # 从链接中提取 video_id（用于去重，只要网站不抽风改id，视频id永久不变）
            mark = re.search(r"v=(\d+)", video_link)
            
            # mark.group(0) 返回整个匹配结果，比如"v=406998"
            # mark.group(1) 返回第一个括号捕获的内容，比如"406998"
            item['video_id'] = mark.group(1)

            # 连续序号（记录当前在网站视频列表中的位置，对应第几个视频）
            item['sort_order'] = current_index
            current_index += 1

            # 列表页已有的字段
            item['video_title'] = video.xpath('.//div[@class="title"]/text()').get('').strip()
            item['video_link'] = video_link.strip()
            item['video_cover'] = video.xpath('.//img[@class="main-thumb"]/@src').get('').strip()
            item['video_duration'] = video.xpath('.//div[@class="duration"]/text()').get('').strip()

            # 1. 一次性提取并清洗所有文本（利用列表推导式）
            stat_texts = [
                text.strip()
                for text in video.xpath('.//div[@class="stats-container"]/div[@class="stat-item"]/text()').getall()
                if text.strip()
            ]
            # 2. 安全地分别赋值（防止网页结构变动导致索引越界报错）
            item['thump_up'] = stat_texts[0] if len(stat_texts) > 0 else None
            item['video_count'] = stat_texts[1] if len(stat_texts) > 1 else None

            item['video_subtitle'] = video.xpath('.//div[@class="subtitle"]/a/text()').get('').strip()
            item['author_link'] = video.xpath('.//div[@class="subtitle"]/a/@href').get('').strip()

            # ── Tier 1：直接 yield，不进详情页 ──
            # 详情页字段补默认值，防止 SQL 绑定参数缺失
            item['video_url_1080p'] = None
            item['video_url_720p'] = None
            item['video_url_480p'] = None
            item['video_poster'] = None
            item['author_name'] = None
            item['author_avatar'] = None
            item['video_tags'] = None

            yield item


        # 看还有后续的页数没有，获取下一页链接（不超过 MAX_LIST_PAGES 页）
        next_page = response.xpath('//form[@id="skip-page-form"]/a[last()]/@href').get('').strip()
        if next_page and next_page != "#" and current_page < MAX_LIST_PAGES:
            yield response.follow(
                url=next_page,
                headers=headers,
                callback=self.parse,
                meta={
                    "proxy": xray_PROXY,
                    "page": current_page + 1,
                    "sort_order": current_index,
                },
            )


    # @staticmethod把该函数变成了一个无状态的工具，不用实例化就能用
    # ── Tier 2：懒惰加载详情页（供播放器调用）───────────────

    @staticmethod
    def crawl_detail(video_id: str) -> dict:
        """
        爬取单个视频的详情页，返回具有时限的字段。
        由播放器在用户点击播放时按需调用。

        返回:
            {
                "video_url_1080p": "...",
                "video_url_720p": "...",
                "video_url_480p": "...",
                "video_poster": "...",
                "author_name": "...",
                "author_avatar": "...",
                "video_tags": [...],
            }
        """
        url = f"https://hanime1.me/watch?v={video_id}"

        try:
            # 拿到视频详情页的 HTML内容（这里注意是request发的请求了）
            resp = requests.get(url, headers=headers, proxies={"http": xray_PROXY}, timeout=15)
        except Exception as e:
            print(f"  crawl_detail 请求失败 [{video_id}]: {e}")
            return {}

        # 通过scrapy包装成选择器对象，这样才能用xpath方法
        sel = scrapy.Selector(text=resp.text)

        result = {
            "video_url_1080p": sel.xpath('//source[@size="1080"]/@src').get('').strip(),
            "video_url_720p": sel.xpath('//source[@size="720"]/@src').get('').strip(),
            "video_url_480p": sel.xpath('//source[@size="480"]/@src').get('').strip(),
            "video_poster": sel.xpath('//video/@poster').get('').strip(),
            "author_name": sel.xpath('//a[@id="video-artist-name"]/text()').get('').strip(),
        }

        # 作者头像
        if result["author_name"]:
            result["author_avatar"] = sel.xpath(
                '//img[contains(@alt, $name)]/@src', name=result["author_name"]
            ).get('').strip()

        # 视频标签（去掉最后两个 +/- 按钮）
        # 1. 先获取所有标签元素的列表（不加getall函数，要不然返回的就是字符串了）
        all_tags = sel.xpath('//div[@class="single-video-tag"]')

        # 2. 切片去掉最后两个，提取纯文本，并对每个文本执行 strip()
        result["video_tags"] = json.dumps(
            [tag.xpath('string(.)').get('').strip() for tag in all_tags[:-2]],
            ensure_ascii=False,
        )

        return result


    





