"""
SageTimePlayer 入口

启动 GUI 主窗口，按配置自动初始化代理。
"""

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from database import settings
from gui.main_window import MainWindow
from gui.themes import get_theme
from path.paths import ensure_data_dirs


def main():
    ensure_data_dirs()  # 确保用户数据目录存在

    # ── 爬虫子进程模式（打包 exe 专用，避免重新打开 GUI） ──
    if "--crawl" in sys.argv:
        _run_crawl_subprocess()
        return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(get_theme("dark"))

    # 确保至少有一条订阅（创建窗口前执行）
    _ensure_subscription()

    window = MainWindow()
    window.show()

    QTimer.singleShot(500, lambda: _on_startup(window))

    sys.exit(app.exec())


def _ensure_subscription():
    """如果 settings 中没有订阅，创建一条占位订阅（URL 为空，由用户填写）"""
    subs = settings.get("subscriptions") or []
    if not subs:
        settings.set("subscriptions", [{
            "id": str(uuid.uuid4()),
            "alias": "默认订阅",
            "url": "",
            "sort": 1,
            "auto_update": 0,
            "last_updated": 0,
            "note": "",
        }])
        settings.set("current_group", "默认订阅")


def _on_startup(window: MainWindow):
    """启动后处理：首次提示 & 自动开启代理"""
    if settings.get("first_time"):
        window.set_status("首次使用？请先选择节点", "#f59e0b")
        settings.set("first_time", False)
    elif settings.get("auto_start_proxy"):
        node_name = settings.get("last_node_name")
        if node_name:
            pass
        else:
            window.set_status("未选择节点，请手动配置", "#f59e0b")


def _run_crawl_subprocess():
    """打包 exe 子进程模式：只跑爬虫，不启动 GUI"""
    import os
    from path.paths import SCRAPY_CORE_DIR
    scrapy_cwd = str(SCRAPY_CORE_DIR)
    os.chdir(scrapy_cwd)
    from scrapy.cmdline import execute
    import sys as _sys
    _sys.argv = ["scrapy", "crawl", "Hanime1_spider", "-s", "LOG_ENABLED=False"]
    try:
        execute()
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
