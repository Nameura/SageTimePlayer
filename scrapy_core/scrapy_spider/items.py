# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

# 自定义的Item类，用于存储爬取到的数据
class Hanime1SpiderItem(scrapy.Item):
    # 视频的唯一ID（从 video_link 中提取），用于去重
    video_id = scrapy.Field()

    # 连续序号，记录视频在网站列表中的顺序
    sort_order = scrapy.Field()

    video_title = scrapy.Field()        # 视频标题
    video_link = scrapy.Field()         # 视频详情页链接
    video_cover = scrapy.Field()        # 视频封面（小的缩略图）
    video_duration = scrapy.Field()     # 视频时长
    thump_up = scrapy.Field()           # 视频点赞率
    video_count = scrapy.Field()        # 视频播放量
    video_subtitle = scrapy.Field()     # 作者·发布时间
    author_link = scrapy.Field()        # 作者链接

    video_url_1080p = scrapy.Field()    # 视频播放链接（1080p）
    video_url_720p = scrapy.Field()     # 视频播放链接（720p）
    video_url_480p = scrapy.Field()     # 视频播放链接（480p）
    video_poster = scrapy.Field()       # 视频海报（大图）
    author_name = scrapy.Field()        # 作者名称
    author_avatar = scrapy.Field()      # 作者头像
    video_tags = scrapy.Field()         # 视频标签



    # TODO:在视频详情页下展示推荐的视频（Hanime1视频详情页也是60个）
