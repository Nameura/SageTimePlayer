"""
视频播放页面

mpv 引擎 + Qt 自绘控制栏（滑动淡入淡出动画）。
顶栏和底栏作为浮层叠加在 mpv 容器之上。
"""

import os
import threading
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPropertyAnimation, QSize, QTimer, Qt, Signal, QPoint,
)
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from gui.clickable_slider import ClickableSlider
from gui.video.mpv_player import MpvPlayer
from gui.icons import load_icon
from gui.toast import Toast

from path.paths import ROOT

BAR_H = 48
BOTTOM_H = 56
ANIM_DURATION = 350


class VideoPlayPage(QWidget):
    """视频播放页面（mpv 引擎 + 自绘控制栏）"""

    back_requested = Signal()
    _detail_ready = Signal(str)
    _detail_failed = Signal()
    _retry_lazy_load = Signal()
    _download_done = Signal(str)
    _download_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._mpv = MpvPlayer()
        self._is_fullscreen = False
        self._toast: Toast | None = None
        self._visible = True
        self._seeking = False
        self._retry_count = 0

        self.setObjectName("videoPlayPage")
        self.setStyleSheet("#videoPlayPage { background: #000; }")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self._detail_ready.connect(self._on_detail_ready)
        self._detail_failed.connect(self._on_detail_fail)
        self._retry_lazy_load.connect(self._on_retry_lazy_load)
        self._download_done.connect(self._on_download_done)
        self._download_error.connect(self._on_download_error)

        self._build_ui()
        self._setup_timer()

        # 全局快捷键
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self._toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._on_esc)

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # ── mpv 容器（填满）─────────────────────────────
        self._mpv_container = QWidget()
        self._mpv_container.setObjectName("mpvContainer")
        self._mpv_container.setStyleSheet("#mpvContainer { background: #000; }")
        self._mpv_container.setMouseTracking(True)
        self._mpv_container.installEventFilter(self)
        self._layout.addWidget(self._mpv_container, stretch=1)

        # ── 顶栏（浮层，父级为 self）────────────────────
        self._top_bar = QWidget(self)
        self._top_bar.setObjectName("topBar")
        self._top_bar.setFixedHeight(BAR_H)
        self._top_bar.setStyleSheet(
            "#topBar { background: rgba(10, 10, 15, 0.80);"
            " border-bottom: 1px solid rgba(255,255,255,0.04); }")
        tl = QHBoxLayout(self._top_bar)
        tl.setContentsMargins(8, 0, 12, 0)

        self._back_btn = QPushButton()
        self._back_btn.setIcon(load_icon("back"))
        self._back_btn.setIconSize(QSize(20, 20))
        self._back_btn.setFlat(True)
        self._back_btn.setStyleSheet(
            "QPushButton { padding: 6px; border-radius: 6px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); }")
        self._back_btn.clicked.connect(self._go_back)
        tl.addWidget(self._back_btn)

        self._title = QLabel("")
        self._title.setStyleSheet("color: #eee; font-size: 14px; font-weight: 500; margin-left: 4px;")
        tl.addWidget(self._title, stretch=1)

        # ── 底栏（浮层，父级为 self）────────────────────
        self._bottom_bar = QWidget(self)
        self._bottom_bar.setObjectName("bottomBar")
        self._bottom_bar.setFixedHeight(BOTTOM_H)
        self._bottom_bar.setStyleSheet(
            "#bottomBar { background: rgba(10, 10, 15, 0.80);"
            " border-top: 1px solid rgba(255,255,255,0.06); }")
        bl = QHBoxLayout(self._bottom_bar)
        bl.setContentsMargins(10, 4, 10, 4)
        bl.setSpacing(6)

        self._play_btn = QPushButton()
        self._play_btn.setIcon(load_icon("play"))
        self._play_btn.setIconSize(QSize(24, 24))
        self._play_btn.setFixedSize(36, 36)
        self._play_btn.setFlat(True)
        self._play_btn.setStyleSheet("QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 18px; }")
        self._play_btn.clicked.connect(self._toggle_play)
        bl.addWidget(self._play_btn)

        self._slider = ClickableSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 1000)
        self._slider.sliderMoved.connect(self._seek)
        self._slider.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self._slider.sliderReleased.connect(lambda: setattr(self, '_seeking', False))
        self._slider.setFixedHeight(8)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,0.12); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ff6b9d; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #ff6b9d; height: 4px; border-radius: 2px; }
        """)
        bl.addWidget(self._slider, stretch=1)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        bl.addWidget(self._time_label)

        self._vol_btn = QPushButton()
        self._vol_btn.setIcon(load_icon("vol_high"))
        self._vol_btn.setIconSize(QSize(18, 18))
        self._vol_btn.setFixedSize(28, 28)
        self._vol_btn.setFlat(True)
        self._vol_btn.setStyleSheet("QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 14px; }")
        self._vol_btn.clicked.connect(self._toggle_mute)
        bl.addWidget(self._vol_btn)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(80)
        self._vol_slider.setFixedWidth(60)
        self._vol_slider.valueChanged.connect(self._set_volume)
        self._vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,0.12); height: 3px; border-radius: 1px; }
            QSlider::handle:horizontal { background: #fff; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }
            QSlider::sub-page:horizontal { background: #fff; height: 3px; border-radius: 1px; }
        """)
        bl.addWidget(self._vol_slider)

        self._quality_box = QHBoxLayout()
        self._quality_box.setSpacing(4)
        bl.addLayout(self._quality_box)

        self._dl_btn = QPushButton()
        self._dl_btn.setIcon(load_icon("download"))
        self._dl_btn.setIconSize(QSize(16, 16))
        self._dl_btn.setFixedSize(28, 28)
        self._dl_btn.setFlat(True)
        self._dl_btn.setStyleSheet("QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 14px; }")
        self._dl_btn.clicked.connect(self._download_video)
        bl.addWidget(self._dl_btn)

        self._fs_btn = QPushButton()
        self._fs_btn.setIcon(load_icon("fullscreen"))
        self._fs_btn.setIconSize(QSize(18, 18))
        self._fs_btn.setFixedSize(28, 28)
        self._fs_btn.setFlat(True)
        self._fs_btn.setStyleSheet("QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 14px; }")
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        bl.addWidget(self._fs_btn)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._top_bar.setFixedWidth(w)
        self._bottom_bar.setFixedWidth(w)

        if not getattr(self, '_resized', False):
            self._resized = True
            # 初始状态：顶栏藏到上方，底栏藏到下方
            self._top_bar.move(0, -BAR_H)
            self._bottom_bar.move(0, h)
            self._visible = False
        elif self._visible:
            self._top_bar.move(0, 0)
            self._bottom_bar.move(0, h - BOTTOM_H)

    # ── 控制栏显隐动画 ─────────────────────────────────

    def _show_bars(self, animated=True):
        self._hide_timer.stop()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self._visible:
            if self._mpv.is_running:
                self._hide_timer.start()
            return
        self._visible = True
        h = self.height()
        if animated:
            self._anim_top = QPropertyAnimation(self._top_bar, b"pos")
            self._anim_top.setEasingCurve(QEasingCurve.Type.OutExpo)
            self._anim_top.setDuration(ANIM_DURATION)
            self._anim_top.setStartValue(QPoint(0, -BAR_H))
            self._anim_top.setEndValue(QPoint(0, 0))
            self._anim_top.start()

            self._anim_bottom = QPropertyAnimation(self._bottom_bar, b"pos")
            self._anim_bottom.setEasingCurve(QEasingCurve.Type.OutExpo)
            self._anim_bottom.setDuration(ANIM_DURATION)
            self._anim_bottom.setStartValue(QPoint(0, h))
            self._anim_bottom.setEndValue(QPoint(0, h - BOTTOM_H))
            self._anim_bottom.start()
        else:
            self._top_bar.move(0, 0)
            self._bottom_bar.move(0, h - BOTTOM_H)
        if self._mpv.is_running:
            self._hide_timer.start()

    def _hide_bars(self):
        if not self._visible:
            return
        self._visible = False
        h = self.height()
        self.setCursor(Qt.CursorShape.BlankCursor)

        self._anim_top = QPropertyAnimation(self._top_bar, b"pos")
        self._anim_top.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._anim_top.setDuration(ANIM_DURATION)
        self._anim_top.setStartValue(QPoint(0, 0))
        self._anim_top.setEndValue(QPoint(0, -BAR_H))
        self._anim_top.start()

        self._anim_bottom = QPropertyAnimation(self._bottom_bar, b"pos")
        self._anim_bottom.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._anim_bottom.setDuration(ANIM_DURATION)
        self._anim_bottom.setStartValue(QPoint(0, h - BOTTOM_H))
        self._anim_bottom.setEndValue(QPoint(0, h))
        self._anim_bottom.start()

    def _setup_timer(self):
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(3000)
        self._hide_timer.timeout.connect(self._hide_bars)

    # ── 事件 ────────────────────────────────────────────

    def eventFilter(self, obj, event):
        t = event.type()
        if obj is self._mpv_container:
            if t == QEvent.Type.MouseMove:
                self._show_bars()
            elif t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._toggle_play()
                return True
        return super().eventFilter(obj, event)

    def mouseMoveEvent(self, event):
        self._show_bars()

    def _on_esc(self):
        if self._is_fullscreen:
            self._toggle_fullscreen()

    # ── 加载 ────────────────────────────────────────────

    def load_video(self, video_data: dict):
        self._data = video_data
        self._retry_count = 0
        self._title.setText(video_data.get("video_title", ""))
        # 首次加载直接显示（无动画）
        self._show_bars(animated=False)

        # 监听播放结束事件（用于检测链接过期）
        def on_playback_end(reason):
            """mpv 播放结束回调，reason 如 'eof'、'error'、'stop'"""
            if reason == "error" and self._retry_count < 2:
                self._retry_lazy_load.emit()

        self._mpv.on_end = on_playback_end

        url = (video_data.get("video_url_1080p")
               or video_data.get("video_url_720p")
               or video_data.get("video_url_480p") or "")

        if url:
            self._start_playback(url)
        else:
            self._title.setText("正在获取播放地址…")
            self._toast = Toast.show_loading("正在爬取视频地址…", self.window())
            threading.Thread(target=self._lazy_load_detail, daemon=True).start()

    def _on_retry_lazy_load(self):
        """播放链接过期，重新惰性爬取"""
        self._retry_count += 1
        self._title.setText("播放地址已过期，正在重新获取…")
        if not self._toast:
            self._toast = Toast.show_loading("正在重新获取播放地址…", self.window())
        threading.Thread(target=self._lazy_load_detail, daemon=True).start()

    # 懒加载视频详情信息
    def _lazy_load_detail(self):
        try:
            video_id = self._data.get("video_id", "")
            if not video_id:
                import re
                m = re.search(r"/watch\?id=(\d+)", self._data.get("video_link", ""))
                video_id = m.group(1) if m else ""
            if video_id:
                import sys
                sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scrapy_core"))
                from scrapy_core.scrapy_spider.spiders.Hanime1_spider import Hanime1SpiderSpider
                detail = Hanime1SpiderSpider.crawl_detail(video_id)
                if detail:
                    self._data.update(detail)
                    from database.database import get_connection, update_hanime1_links
                    conn = get_connection()
                    update_hanime1_links(conn, video_id, **detail)
                    conn.close()
                    url = (detail.get("video_url_1080p") or detail.get("video_url_720p")
                           or detail.get("video_url_480p") or "")
                    if url:
                        self._detail_ready.emit(url)
                        return
            self._detail_failed.emit()
        except Exception as e:
            print(f"惰性加载失败: {e}")
            self._on_detail_fail()

    def _on_detail_ready(self, url: str):
        if self._toast:
            self._toast.close()
        self._title.setText(self._data.get("video_title", ""))
        self._start_playback(url)
        self._rebuild_quality()

    def _on_detail_fail(self):
        if self._toast:
            self._toast.close()
        Toast.show_message("⚠ 无法获取播放地址", "error", 3000, self.window())

    def _rebuild_quality(self):
        for btn in self._quality_btns:
            btn.deleteLater()
        self._quality_btns.clear()
        for key, label in [("video_url_1080p", "1080p"), ("video_url_720p", "720p"), ("video_url_480p", "480p")]:
            if self._data.get(key):
                btn = QPushButton(label)
                btn.setFixedHeight(24)
                btn.setStyleSheet("QPushButton { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.06); color: #ddd; } QPushButton:hover { background: #ff6b9d; color: #fff; }")
                btn.clicked.connect(lambda checked, k=key: self._switch_quality(k))
                self._quality_box.addWidget(btn)
                self._quality_btns.append(btn)
    _quality_btns: list = []

    # ── 播放 ────────────────────────────────────────────

    def _start_playback(self, url: str):
        hwnd = int(self._mpv_container.winId())
        self._mpv.set_container(hwnd)
        ok = self._mpv.start(url)
        if not ok:
            Toast.show_message("⚠ 无法启动 mpv 播放器", "error", 3000, self.window())
            return
        # 开始播放 → 按钮图标改为暂停
        self._play_btn.setIcon(load_icon("pause"))
        # 轮询进度
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(250)
        self._update_timer.timeout.connect(self._poll_position)
        self._update_timer.start()

    def _poll_position(self):
        if not self._mpv.is_running:
            self._update_timer.stop()
            return
        pos = self._mpv.time_pos or 0
        dur = self._mpv.duration or 0
        if dur > 0 and not self._seeking:
            self._slider.blockSignals(True)
            self._slider.setValue(int(pos / dur * 1000))
            self._slider.blockSignals(False)
        self._time_label.setText(f"{int(pos)//60:02d}:{int(pos)%60:02d} / {int(dur)//60:02d}:{int(dur)%60:02d}")

    def _toggle_play(self):
        if not self._mpv.is_running:
            return
        self._mpv.toggle_play()
        self._play_btn.setIcon(load_icon("play" if self._mpv.paused else "pause"))

    def _seek(self, pos: int):
        if self._mpv.is_running:
            dur = self._mpv.duration
            if dur > 0:
                self._mpv.seek(int(pos / 1000 * dur * 1000))

    def _switch_quality(self, key: str):
        url = self._data.get(key, "")
        if url:
            self._mpv.restart(url)

    def _toggle_mute(self):
        if not self._mpv.is_running:
            return
        self._mpv.toggle_mute()
        self._vol_btn.setIcon(load_icon("vol_mute" if self._mpv.muted else "vol_high"))

    def _set_volume(self, val: int):
        if not self._mpv.is_running:
            return
        self._mpv.volume = val / 100.0
        self._mpv.muted = (val == 0)
        self._vol_btn.setIcon(load_icon("vol_mute" if val == 0 else "vol_high"))

    def _toggle_fullscreen(self):
        w = self.window()
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            w.showFullScreen()
            self._fs_btn.setIcon(load_icon("fullscreen_exit"))
        else:
            w.showNormal()
            self._fs_btn.setIcon(load_icon("fullscreen"))
            self._show_bars()

    def _download_video(self):
        """选择画质 → 选择保存路径 → 开始下载"""
        # 收集可用画质
        qualities = []
        for key, label in [("video_url_1080p", "1080p"), ("video_url_720p", "720p"), ("video_url_480p", "480p")]:
            url = self._data.get(key, "")
            if url:
                qualities.append((label, url))
        if not qualities:
            Toast.show_message("⚠ 暂无可用下载地址", "error", 2000, self.window())
            return

        # 选择画质
        if len(qualities) == 1:
            chosen_label, chosen_url = qualities[0]
        else:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QFrame

            dlg = QDialog(self.window())
            dlg.setWindowTitle("下载视频")
            dlg.setFixedSize(300, 360)
            dlg.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            # 圆角裁剪容器
            container = QFrame(dlg)
            container.setObjectName("dlgContainer")
            container.setStyleSheet("""
                #dlgContainer {
                    background: #16181f;
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 16px;
                }
            """)
            container.setGeometry(0, 0, 300, 360)

            vl = QVBoxLayout(container)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(0)

            # ── 顶部标题区 ──
            header = QFrame()
            header.setFixedHeight(72)
            header.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 16px 16px 0 0;")
            hl = QVBoxLayout(header)
            hl.setContentsMargins(24, 0, 24, 0)

            title_label = QLabel("下载视频")
            title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #fff; background: transparent;")
            hl.addWidget(title_label)

            sub_label = QLabel("选择要下载的画质")
            sub_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
            hl.addWidget(sub_label)

            vl.addWidget(header)

            # ── 画质按钮区 ──
            body = QFrame()
            body.setStyleSheet("background: transparent;")
            bl = QVBoxLayout(body)
            bl.setContentsMargins(20, 24, 20, 0)
            bl.setSpacing(18)

            quality_labels = {"1080p": "HD", "720p": "SD", "480p": "LD"}
            for label, url in qualities:
                btn = QPushButton()
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(52)
                btn.setAttribute(Qt.WidgetAttribute.WA_Hover)
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255,255,255,0.04);
                        border: 1px solid rgba(255,255,255,0.06);
                        border-radius: 12px;
                    }
                    QPushButton:hover {
                        background: rgba(255,107,157,0.15);
                        border: 1px solid rgba(255,107,157,0.35);
                    }
                """)
                btn_layout = QHBoxLayout(btn)
                btn_layout.setContentsMargins(16, 0, 16, 0)
                btn_layout.setSpacing(14)

                badge = QLabel(quality_labels.get(label, "HQ"))
                badge.setFixedSize(40, 26)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setStyleSheet("""
                    background: rgba(255,107,157,0.15);
                    color: #ff6b9d;
                    border-radius: 8px;
                    font-size: 11px;
                    font-weight: 700;
                """)
                btn_layout.addWidget(badge)

                name_lbl = QLabel(label)
                name_lbl.setStyleSheet("color: #eee; font-size: 14px; font-weight: 500; background: transparent;")
                btn_layout.addWidget(name_lbl)

                btn_layout.addStretch()

                arrow_lbl = QLabel("›")
                arrow_lbl.setStyleSheet("color: #555; font-size: 20px; font-weight: 300; background: transparent;")
                btn_layout.addWidget(arrow_lbl)

                btn.clicked.connect(lambda checked, u=url, l=label: (
                    setattr(dlg, '_url', u), setattr(dlg, '_label', l), dlg.accept()
                ))
                bl.addWidget(btn)

            vl.addWidget(body, stretch=1)

            # ── 底部 ──
            footer = QFrame()
            footer.setStyleSheet("background: transparent;")
            fl = QVBoxLayout(footer)
            fl.setContentsMargins(20, 16, 20, 20)
            fl.setSpacing(12)

            # 分割线
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: rgba(255,255,255,0.04); border: none;")
            fl.addWidget(sep)

            cancel_btn = QPushButton("取消")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setFixedHeight(40)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.04);
                    color: #888;
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 10px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.08);
                    color: #ddd;
                }
            """)
            cancel_btn.clicked.connect(dlg.reject)
            fl.addWidget(cancel_btn)

            vl.addWidget(footer)

            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            chosen_url = dlg._url
            chosen_label = dlg._label

        # 选择保存路径
        from PySide6.QtWidgets import QFileDialog
        default_name = self._data.get("video_title", "video") or "video"
        # 过滤非法文件名字符
        for ch in r'\/:*?"<>|':
            default_name = default_name.replace(ch, "_")
        save_path, _ = QFileDialog.getSaveFileName(
            self.window(), "保存视频", str(Path.home() / "Downloads" / f"{default_name}_{chosen_label}.mp4"),
            "MP4 视频 (*.mp4);;所有文件 (*.*)"
        )
        if not save_path:
            return

        # 开始下载
        self._toast = Toast.show_loading(f"正在下载 {chosen_label}…", self.window())

        def task():
            import requests
            try:
                resp = requests.get(chosen_url, stream=True, timeout=30,
                                    headers={"Referer": "https://hanime1.me",
                                             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/149.0.0.0"},
                                    proxies={"http": "http://127.0.0.1:10909"})
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 8192
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                self._download_done.emit(save_path)
            except Exception as e:
                self._download_error.emit(str(e))

        threading.Thread(target=task, daemon=True).start()

    def _on_download_done(self, path: str):
        """下载完成"""
        if self._toast:
            self._toast.close()
        Toast.show_message(f"✅ 下载完成", "success", 3000, self.window())

    def _on_download_error(self, msg: str):
        """下载失败"""
        if self._toast:
            self._toast.close()
        Toast.show_message(f"❌ 下载失败: {msg}", "error", 3000, self.window())

    def _go_back(self):
        self._mpv.stop()
        if self._toast:
            self._toast.close()
        self._hide_timer.stop()
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        if self._is_fullscreen:
            self.window().showNormal()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._visible = True
        self._top_bar.move(0, 0)
        self._top_bar.show()
        self._bottom_bar.move(0, self.height() - BOTTOM_H)
        self._bottom_bar.show()
        self._title.setText("")
        self.back_requested.emit()
