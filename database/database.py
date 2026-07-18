"""
数据库管理模块

负责 SQLite 数据库的连接管理、建表、基本 CRUD 操作。
所有采集站的数据表都在此维护。

用法：
  from database.database import get_connection, init_hanime1_table
  conn = get_connection()
  init_hanime1_table()
"""

import sqlite3

from path.paths import DATA_DATABASE_DIR

# ── 路径 ────────────────────────────────────────────────
DB_PATH = DATA_DATABASE_DIR / "scrapy_data.db"


# ── 连接 ────────────────────────────────────────────────


def get_connection() -> sqlite3.Connection:
    """获取数据库连接（自动创建 db 文件）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # 支持按列名访问
    conn.execute(
        "PRAGMA journal_mode=WAL"
    )  # 预写日志模式提高并发写入性能（高频写入的时候不会锁库）
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── 建表 ────────────────────────────────────────────────


def init_hanime1_table():
    """创建/验证 hanime1_videos 表（幂等）"""
    sql = """
    CREATE TABLE IF NOT EXISTS hanime1_videos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id        TEXT    UNIQUE NOT NULL,
        sort_order      INTEGER NOT NULL,
        video_title     TEXT,
        video_link      TEXT,
        video_cover     TEXT,
        video_duration  TEXT,
        thump_up        TEXT,
        video_count     TEXT,
        video_subtitle  TEXT,
        author_link     TEXT,
        video_url_1080p TEXT,
        video_url_720p  TEXT,
        video_url_480p  TEXT,
        video_poster    TEXT,
        author_name     TEXT,
        author_avatar   TEXT,
        video_tags      TEXT,
        crawled_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    # TIMESTAMP专门用来存储日期和时间（YYYY-MM-DD HH:MM:SS），默认值为当前时间戳

    conn = get_connection()
    conn.execute(sql)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hanime1_sort_order ON hanime1_videos(sort_order)")
    conn.commit()
    conn.close()


# ── 工具函数 ─────────────────────────────────────────────
# upsert指的是更新(update) + 插入(insert)，当记录存在时更新，不存在时插入的操作

def upsert_hanime1_video(conn: sqlite3.Connection, item: dict):
    """
    插入或更新一条 hanime1 视频记录。

    由 pipeline 调用。列表页全量爬时更新所有字段（含 sort_order），
    懒加载更新时只更新链接字段（不碰 sort_order）。
    """
    sql = """
    INSERT INTO hanime1_videos (
        video_id, sort_order,
        video_title, video_link, video_cover, video_duration,
        thump_up, video_count, video_subtitle, author_link,
        video_url_1080p, video_url_720p, video_url_480p,
        video_poster, author_name, author_avatar, video_tags
    ) VALUES (
        :video_id, :sort_order,
        :video_title, :video_link, :video_cover, :video_duration,
        :thump_up, :video_count, :video_subtitle, :author_link,
        :video_url_1080p, :video_url_720p, :video_url_480p,
        :video_poster, :author_name, :author_avatar, :video_tags
    )
    ON CONFLICT(video_id) DO UPDATE SET
        sort_order      = COALESCE(excluded.sort_order, hanime1_videos.sort_order),
        video_title     = COALESCE(excluded.video_title, hanime1_videos.video_title),
        video_link      = COALESCE(excluded.video_link, hanime1_videos.video_link),
        video_cover     = COALESCE(excluded.video_cover, hanime1_videos.video_cover),
        video_duration  = COALESCE(excluded.video_duration, hanime1_videos.video_duration),
        thump_up        = COALESCE(excluded.thump_up, hanime1_videos.thump_up),
        video_count     = COALESCE(excluded.video_count, hanime1_videos.video_count),
        video_subtitle  = COALESCE(excluded.video_subtitle, hanime1_videos.video_subtitle),
        author_link     = COALESCE(excluded.author_link, hanime1_videos.author_link),
        video_url_1080p = COALESCE(excluded.video_url_1080p, hanime1_videos.video_url_1080p),
        video_url_720p  = COALESCE(excluded.video_url_720p, hanime1_videos.video_url_720p),
        video_url_480p  = COALESCE(excluded.video_url_480p, hanime1_videos.video_url_480p),
        video_poster    = COALESCE(excluded.video_poster, hanime1_videos.video_poster),
        author_name     = COALESCE(excluded.author_name, hanime1_videos.author_name),
        author_avatar   = COALESCE(excluded.author_avatar, hanime1_videos.author_avatar),
        video_tags      = COALESCE(excluded.video_tags, hanime1_videos.video_tags)
        -- 注意: crawled_at 不由列表页 UPSERT 更新，
        -- 只由 update_hanime1_links（懒加载）刷新
    ;
    """
    conn.execute(sql, item)


def update_hanime1_links(conn: sqlite3.Connection, video_id: str, **fields):
    """
    懒加载时只刷新链接字段，不更新 sort_order。

    用法：
      update_hanime1_links(conn, "406998",
          video_url_1080p="...", video_cover="...")
    """
    if not fields:
        return
    
    # 下面相当于一个UPDATE语句生成器
    # **fields 会收集所有 key=value 参数变成字典
    set_clause = ", ".join(f"{k} = ?" for k in fields) # 遍历fields字典的key，生成类似 "video_url_1080p = ?, video_cover = ?" 的字符串
    values = list(fields.values()) + [video_id] # 拼接参数列表
    conn.execute(
        f"""
        UPDATE hanime1_videos
        SET {set_clause}, crawled_at = CURRENT_TIMESTAMP
        WHERE video_id = ?
    """,
        values,
    )
    conn.commit()
