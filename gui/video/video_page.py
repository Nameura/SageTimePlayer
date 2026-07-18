"""
视频浏览页面

封面网格展示 + 搜索 + 分页 + 按需加载详情。
"""

import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
import requests

from gui.video.cover_card import CoverCard
from gui.flow_layout import FlowLayout
from gui.themes import set_smooth_scroll
from gui.toast import Toast
from database import settings
from database.database import init_hanime1_table
# VideoPlayerWindow 不再直接使用，改为主窗口内的 VideoPlayPage


# 数据库查询
def _query_videos(where_clause: str = "", params: tuple = ()) -> list:
    from database.database import get_connection
    try:
        conn = get_connection()
        sql = "SELECT * FROM hanime1_videos " + where_clause + " ORDER BY sort_order ASC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


class VideoPage(QWidget):
    """视频浏览主页面"""

    status_changed = Signal(str, str)
    play_requested = Signal(object)  # 发射 video_data 字典给主窗口
    _videos_loaded_signal = Signal(object)  # 跨线程传递视频列表
    _cover_loaded_signal = Signal(object, object)  # (card, pixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_videos: list[dict] = []
        self._filtered: list[dict] = []
        self._card_widgets: list[CoverCard] = []
        self._toast_load = None
        self._initial_load = True  # 首次加载，不弹 Toast

        self._videos_loaded_signal.connect(self._on_videos_loaded)
        self._cover_loaded_signal.connect(self._on_cover_loaded)

        self._build_ui()
        # 确保数据库表存在
        init_hanime1_table()
        # 延迟加载，等窗口 HWND 就绪
        QTimer.singleShot(0, self._load_videos)

        # ── 封面定时刷新（每 1 小时检查，24 小时执行一次） ──
        self._cover_refresh_timer = QTimer(self)
        self._cover_refresh_timer.timeout.connect(self._check_cover_refresh)
        self._cover_refresh_timer.start(3_600_000)  # 1 小时

    def _check_cover_refresh(self):
        """如果距上次封面刷新超过 24 小时，静默爬取最新"""
        last = settings.get("last_cover_refresh") or 0
        if time.time() - last < 86400:  # 24 小时
            return

        def task():
            import subprocess, sys, os
            from path.paths import SCRAPY_CORE_DIR
            scrapy_cwd = str(SCRAPY_CORE_DIR)
            try:
                if getattr(sys, 'frozen', False):
                    subprocess.run(
                        [sys.executable, "--crawl", "Hanime1_spider", "-s", "LOG_ENABLED=False"],
                        cwd=scrapy_cwd,
                        capture_output=True, text=True, timeout=120,
                    )
                else:
                    subprocess.run(
                        [sys.executable, "-m", "scrapy", "crawl", "Hanime1_spider",
                         "-s", "LOG_ENABLED=False"],
                        cwd=scrapy_cwd,
                        capture_output=True, text=True, timeout=120,
                    )
                settings.set("last_cover_refresh", time.time())
                rows = _query_videos()
                self._videos_loaded_signal.emit(rows)
            except Exception as e:
                print(f"[封面刷新] 失败: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # ── 顶部栏 ──────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索视频标题…")
        self._search_input.setFixedWidth(260)
        self._search_input.textChanged.connect(self._filter_videos)
        top_bar.addWidget(self._search_input)

        top_bar.addStretch()

        self._refresh_btn = QPushButton("🔄 刷新列表")
        self._refresh_btn.setFixedHeight(34)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._load_videos)
        top_bar.addWidget(self._refresh_btn)

        # 后台爬虫刷新按钮（调用 scripts/refresh_hanime1.py）
        self._crawl_btn = QPushButton("⬇ 爬取最新")
        self._crawl_btn.setFixedHeight(34)
        self._crawl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._crawl_btn.clicked.connect(self._run_crawl_refresh)
        top_bar.addWidget(self._crawl_btn)

        layout.addLayout(top_bar)

        # ── 统计 ────────────────────────────────────────
        self._info_label = QLabel("加载中…")
        self._info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._info_label)

        # ── 空状态占位 ──────────────────────────────────
        self._empty_placeholder = QLabel("还没有视频数据\n点击上方「⬇ 爬取最新」爬取 Hanime1 视频")
        self._empty_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_placeholder.setStyleSheet("color: #555; font-size: 16px; padding: 40px 60px 80px;")
        self._empty_placeholder.hide()
        layout.addWidget(self._empty_placeholder, stretch=1)

        # ── 封面网格（Flow-like，用 QScrollArea 包裹） ──
        self._scroll = QScrollArea()
        self._scroll.setObjectName("videoScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            #videoScroll {
                background: transparent;
                border: none;
            }
        """)

        self._grid_container = QWidget()
        self._grid_container.setObjectName("gridContainer")
        self._grid_container.setStyleSheet("""
            #gridContainer {
                background: transparent;
            }
            #gridContainer #coverCard {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 10px;
            }
            #gridContainer #coverCard:hover {
                background: rgba(255, 255, 255, 0.08);
                border-color: rgba(100, 140, 255, 0.3);
            }
        """)
        self._grid_layout = FlowLayout(self._grid_container, margin=16, spacing=16)

        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll, stretch=1)
        set_smooth_scroll(self._scroll)

    def _load_videos(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("加载中…")
        if not self._initial_load:
            self._toast_load = Toast.show_loading("正在刷新视频列表", self.window())

        def task():
            rows = _query_videos()
            self._videos_loaded_signal.emit(rows)

        threading.Thread(target=task, daemon=True).start()

    def _on_videos_loaded(self, rows):
        self._all_videos = rows
        self._filtered = rows
        self._rebuild_grid()
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("🔄 刷新列表")
        self._crawl_btn.setEnabled(True)
        self._crawl_btn.setText("⬇ 爬取最新")

        if rows:
            self._empty_placeholder.hide()
            self._scroll.show()
            self.status_changed.emit(f"已加载 {len(rows)} 个视频", "#22c55e")
            msg = f"共 {len(rows)} 个视频"
        else:
            self._scroll.hide()
            self._empty_placeholder.show()
            self.status_changed.emit("暂无视频数据，请先爬取", "#f59e0b")
            msg = "暂无视频数据"

        if self._toast_load:
            self._toast_load.close()
            self._toast_load = None
        if not self._initial_load:
            Toast.show_message(msg, "info" if not rows else "success", 2000, self.window())
        self._initial_load = False

    def _filter_videos(self, text: str):
        text = text.lower().strip()
        if not text:
            self._filtered = self._all_videos
        else:
            self._filtered = [
                v for v in self._all_videos
                if text in v.get("video_title", "").lower()
            ]
        self._rebuild_grid()

    def _rebuild_grid(self):
        if not self._filtered:
            # 清除旧卡片
            for c in self._card_widgets:
                self._grid_layout.removeWidget(c)
                c.deleteLater()
            self._card_widgets.clear()
            return

        card_w, card_h = 240, 200

        # 构建全部卡片（创建时即设好父容器）
        new_cards = []
        for v in self._filtered:
            card = CoverCard(
                sort_order=v.get("sort_order", 0),
                title=v.get("video_title", ""),
                cover_url=v.get("video_cover", ""),
                duration=v.get("video_duration", ""),
                thump_up=v.get("thump_up", ""),
                video_count=v.get("video_count", ""),
                subtitle=v.get("video_subtitle", ""),
                parent=self._grid_container,
            )
            card.setFixedSize(card_w, card_h)
            card.clicked.connect(self._on_card_clicked)
            new_cards.append(card)

        # 批量替换布局
        self._card_widgets.clear()
        self._grid_layout.batch_set_items(new_cards, parent_already_set=True)
        self._card_widgets = new_cards

        # 封面下载
        self._start_cover_loads(new_cards)

        # 更新统计
        total = len(self._all_videos)
        shown = len(self._filtered)
        self._info_label.setText(f"共 {total} 视频 | 显示 {shown}")

    def _load_cover(self, card: CoverCard, url: str):
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(resp.content)
                if not pixmap.isNull():
                    self._cover_loaded_signal.emit(card, pixmap)
        except Exception:
            pass

    def _on_cover_loaded(self, card: CoverCard, pixmap: QPixmap):
        """封面加载完成 → 设置图片，若卡片已被销毁则忽略"""
        try:
            card.set_cover(pixmap)
        except RuntimeError:
            pass  # C++ 对象已删除

    def _start_cover_loads(self, cards: list):
        """用线程池控制封面下载并发"""
        from concurrent.futures import ThreadPoolExecutor
        urls = []
        for c in cards:
            url = c._cover_url  # 直接从 card 取
            if url:
                urls.append((c, url))
        if not urls:
            return
        pool = ThreadPoolExecutor(max_workers=6)
        for card, url in urls:
            pool.submit(self._load_cover, card, url)
        pool.shutdown(wait=False)

    def _on_card_clicked(self, sort_order: int):
        """点击卡片 - 切换到播放页"""
        for v in self._all_videos:
            if v.get("sort_order") == sort_order:
                title = v.get("video_title", "?")
                self.status_changed.emit(f"打开: {title}", "#648cff")
                self.play_requested.emit(v)
                break

    # ── 后台爬虫刷新 ───────────────────────────────────

    def _run_crawl_refresh(self):
        self._crawl_btn.setEnabled(False)
        self._crawl_btn.setText("爬取中…")
        self.status_changed.emit("正在爬取最新视频…", "#f59e0b")
        self._toast_load = Toast.show_loading("正在爬取最新视频…", self.window())

        def task():
            import subprocess, sys, os
            from path.paths import SCRAPY_CORE_DIR
            scrapy_cwd = str(SCRAPY_CORE_DIR)
            if getattr(sys, 'frozen', False):
                # 打包环境：通过子进程 + --crawl 参数运行爬虫，不弹 GUI
                result = subprocess.run(
                    [sys.executable, "--crawl"],
                    cwd=scrapy_cwd,
                    capture_output=True, text=True, timeout=120,
                )
            else:
                # 开发环境：子进程方式
                result = subprocess.run(
                    [sys.executable, "-m", "scrapy", "crawl", "Hanime1_spider",
                     "-s", "LOG_ENABLED=False"],
                    cwd=scrapy_cwd,
                    capture_output=True, text=True, timeout=120,
                )
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                print(f"[爬虫子进程] 退出码={result.returncode}, 错误={err[:500]}")
            self._videos_loaded_signal.emit(_query_videos())

        threading.Thread(target=task, daemon=True).start()
