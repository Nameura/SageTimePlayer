# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import sys
from pathlib import Path
from itemadapter import ItemAdapter
import json

from path.paths import ROOT

# 将项目根目录加入 Python 路径（database/ 在项目根目录下）
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Jsonl格式写入的管道

class Hanime1SpiderJsonlPipeline:
    # 爬虫启动时，打开文件
    def open_spider(self, spider):
        from path.paths import DATA_DIR
        # 写入用户数据目录（打包环境下 _internal 只读，所以用 DATA_DIR）
        self.save_dir_json = DATA_DIR / 'jsonl_backup'
        
        # 2. 如果文件夹不存在，则自动创建（parents=True 表示会创建多级目录，exist_ok=True 表示已存在也不报错）
        self.save_dir_json.mkdir(parents=True, exist_ok=True)
        
        # 3. 拼接完整的文件路径
        self.file_path = self.save_dir_json / "Hanime1_videos.jsonl"
        
        # 4. 打开文件准备写入,w模式直接覆盖，不用a追加模式，以后再考虑去重机制（TODO）
        self.file = open(self.file_path, 'w', encoding='utf-8')

        
    # 核心处理：每收到一个 item，就转成 JSON 并写入文件
    def process_item(self, item, spider):
        # 只处理 Hanime1SpiderItem，其他类型跳过
        from scrapy_spider.items import Hanime1SpiderItem
        if not isinstance(item, Hanime1SpiderItem):
            return item
        
        # 将 item 转换为 JSON 字符串并写入，ensure_ascii=False 保证中文正常显示
        try:
            line = json.dumps(dict(item), ensure_ascii=False) + "\n"
            self.file.write(line)
        except Exception:
            pass  # JSONL 写入失败不影响 SQLite 管道
        return item
    
    
    # 爬虫结束时，关闭文件
    def close_spider(self, spider):
        try:
            self.file.close()
        except Exception:
            pass


# ── SQLite 写入（主力存储）──────────────────────────────

class Hanime1SpiderSqlitePipeline:
    """将 Hanime1SpiderItem UPSERT 到 SQLite 数据库"""

    def open_spider(self, spider):
        from database.database import get_connection, init_hanime1_table
        init_hanime1_table()
        self.conn = get_connection()

    def process_item(self, item, spider):
        # 只处理 Hanime1SpiderItem，其他类型跳过
        from scrapy_spider.items import Hanime1SpiderItem
        if not isinstance(item, Hanime1SpiderItem):
            return item

        from database.database import upsert_hanime1_video
        data = dict(item)

        # video_tags 是列表，转为 JSON 字符串存储(旧的json转换逻辑，现在爬虫是触发不了的)
        if isinstance(data.get("video_tags"), list):
            import json as _json
            data["video_tags"] = _json.dumps(data["video_tags"], ensure_ascii=False)

        upsert_hanime1_video(self.conn, data)
        self.conn.commit()
        return item

    def close_spider(self, spider):
        self.conn.close()