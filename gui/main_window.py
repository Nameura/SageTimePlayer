"""
主窗口

采用左侧固定侧边栏 + 右侧 QStackedWidget 的布局。
支持亮色/暗色双主题切换。
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.sidebar import Sidebar
from gui.proxy.proxy_data import ProxyManager
from gui.proxy.proxy_page import ProxyPage
from gui.video.video_page import VideoPage
from gui.video.video_play_page import VideoPlayPage
from gui.toast import Toast


class MainWindow(QWidget):
    """应用主窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SageTimePlayer")
        self.setObjectName("mainWindow")
        self.resize(1200, 800)

        # 允许窗口拉伸
        self.setMinimumSize(900, 600)

        # 全局代理管理器
        self.proxy_manager = ProxyManager()

        # ── 顶层布局 ────────────────────────────────────
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 左侧侧边栏
        self.sidebar = Sidebar(self)
        root_layout.addWidget(self.sidebar)

        # 右侧内容区域（含顶栏 + 页面）
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_panel.setStyleSheet("""
            #rightPanel {
                background: rgba(23, 33, 43, 0.85);
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ── 顶栏 ────────────────────────────────────────
        self._top_bar = self._create_top_bar()
        right_layout.addWidget(self._top_bar)

        # ── 页面容器（QStackedWidget） ───────────────────
        self.pages = QStackedWidget()
        self.pages.setObjectName("pageContainer")
        right_layout.addWidget(self.pages, stretch=1)

        root_layout.addWidget(right_panel, stretch=1)

        # ── 真实页面 ────────────────────────────────────
        self.proxy_page = ProxyPage(self.proxy_manager)
        self.video_page = VideoPage()
        self.video_play_page = VideoPlayPage()
        self.pages.addWidget(self.proxy_page)       # index 0 - 代理
        self.pages.addWidget(self.video_page)       # index 1 - 视频列表
        self.pages.addWidget(self.video_play_page)  # index 2 - 视频播放

        # ── 信号连接 ────────────────────────────────────
        self.sidebar.page_changed.connect(self._on_sidebar_changed)
        self.sidebar.settings_clicked.connect(self._on_settings_clicked)
        self.proxy_page.status_changed.connect(self.set_status)
        self.video_page.status_changed.connect(self.set_status)
        self.video_page.play_requested.connect(self._open_video_player)
        self.video_play_page.back_requested.connect(self._close_video_player)

    # ─────────────────────────────────────────────────────
    #  顶栏
    # ─────────────────────────────────────────────────────
    def _create_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(48)
        bar.setStyleSheet("""
            #topBar {
                background: rgba(24, 26, 32, 0.85);
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        self._page_title = QLabel("代理")
        self._page_title.setStyleSheet("color: #ddd; font-size: 15px; font-weight: 600;")
        layout.addWidget(self._page_title)

        layout.addStretch()

        # 状态指示
        self._status_label = QLabel("● 就绪")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._status_label)

        return bar

    def _make_placeholder(self, text: str) -> QWidget:
        w = QWidget()
        w.setObjectName("placeholder")
        w.setStyleSheet("""
            #placeholder {
                background: transparent;
            }
        """)
        layout = QVBoxLayout(w)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #555; font-size: 28px; font-weight: 300;")
        layout.addWidget(lbl)
        return w

    # ─────────────────────────────────────────────────────
    #  页面切换
    # ─────────────────────────────────────────────────────
    _PAGE_TITLES = ["代理", "视频", ""]

    def _on_sidebar_changed(self, index: int):
        # 侧边栏点击不进入播放页（播放页通过卡片点击进入）
        if index == 2:
            return
        self.pages.setCurrentIndex(index)
        if 0 <= index < len(self._PAGE_TITLES):
            self._page_title.setText(self._PAGE_TITLES[index])
        self.sidebar.setVisible(True)
        self._top_bar.setVisible(True)

    def _open_video_player(self, video_data: dict):
        """从视频列表切换到播放页"""
        self.sidebar.setVisible(False)
        self._top_bar.setVisible(False)
        try:
            self.video_play_page.load_video(video_data)
            self.pages.setCurrentIndex(2)
            self.video_play_page.setFocus()
        except Exception as e:
            self.sidebar.setVisible(True)
            self._top_bar.setVisible(True)
            self.toast(f"打开播放器失败: {e}", "error", 3000)

    def _close_video_player(self):
        """从播放页返回视频列表"""
        self.sidebar.setVisible(True)
        self._top_bar.setVisible(True)
        self.pages.setCurrentIndex(1)

    # ─────────────────────────────────────────────────────
    #  对外接口
    # ─────────────────────────────────────────────────────
    def set_page_title(self, title: str):
        self._page_title.setText(title)

    def set_status(self, text: str, color: str = "#666"):
        self._status_label.setText(f"● {text}")
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def show_loading(self, loading: bool):
        """显示/隐藏加载状态（保留接口，待实现）"""
        pass

    def _on_settings_clicked(self):
        """设置按钮 - 未实现"""
        Toast.show_message("⚙ 设置功能还未完善", "info", 2000, self)

    # ── Toast 消息提示 ─────────────────────────────────

    def toast(self, text: str, type: str = "info", duration: int = 2000):
        """显示浮动消息提示"""
        return Toast.show_message(text, type, duration, self)

    def toast_loading(self, text: str):
        """显示加载提示（不自动消失，需手动关闭）"""
        return Toast.show_loading(text, self)

    def closeEvent(self, event: QCloseEvent):
        """关闭窗口时强制退出（不等待任何资源）"""
        event.accept()
        # 先清理代理（写注册表禁用系统代理 + 等待核心进程完全退出）
        from proxy.launch_v2ray import proxy_off
        proxy_off()
        try:
            self._pm.stop()
        except Exception:
            pass
        # 尽量释放 mpv 资源
        try:
            mpv_player = self._video_play_page._mpv
            if mpv_player:
                mpv_player.stop()
        except Exception:
            pass
        Toast.clear_all()
        # 让 Qt 完成窗口关闭的收尾工作，防止 --windowed 下未响应
        QApplication.processEvents()
        os._exit(0)
