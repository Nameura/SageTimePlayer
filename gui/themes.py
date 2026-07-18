"""
Telegram 风格暗色主题

配色参考 Telegram Desktop 暗色模式：
- 背景: #0E1621 / #17212B
- 表面: #242F3D
- 强调: #2AABEE (Telegram 蓝)
- 文字: #FFFFFF / #A2ACB9
"""

from PySide6.QtCore import Qt, QEvent, QObject, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QScroller, QScrollArea


class _SmoothWheelFilter:
    """让滚轮滑动变成平滑动画"""

    def __init__(self, scroll_area: QScrollArea):
        self._scroll_area = scroll_area
        self._anim: QPropertyAnimation | None = None

    def handle_wheel(self, source, event) -> bool:
        scrollbar = self._scroll_area.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta == 0:
            return False
        target = scrollbar.value() - delta
        target = max(scrollbar.minimum(), min(scrollbar.maximum(), target))
        # 如果已有动画在跑，从中止位置继续
        start = scrollbar.value()
        if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
            start = self._anim.endValue()
        self._anim = QPropertyAnimation(scrollbar, b"value")
        self._anim.setDuration(400)
        self._anim.setStartValue(start)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuint)
        self._anim.start()
        return True

DARK_THEME = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
    color: #ffffff;
    background: transparent;
}

/* ── 滚动条 ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.08);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,0.14);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.08);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255,255,255,0.14);
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal { width: 0; }

/* ── 输入框 ─────────────────────────────────────── */
QLineEdit {
    background: #242F3D;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 6px;
    padding: 7px 12px;
    color: #ffffff;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #2AABEE;
}

/* ── 下拉框 ─────────────────────────────────────── */
QComboBox {
    background: #242F3D;
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 6px;
    padding: 7px 12px;
    color: #ffffff;
    font-size: 13px;
}
QComboBox:hover { background: #2B3848; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #17212B;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    padding: 4px;
    color: #ffffff;
    selection-background-color: #2AABEE;
    outline: none;
}

/* ── 按钮（Telegram 蓝） ────────────────────────── */
QPushButton {
    background: #2AABEE;
    border: none;
    border-radius: 6px;
    padding: 7px 18px;
    color: #ffffff;
    font-size: 13px;
}
QPushButton:hover { background: #3BB3F0; }
QPushButton:pressed { background: #1B8BC6; }
QPushButton:disabled {
    background: rgba(255,255,255,0.04);
    color: #555;
}
QPushButton:flat {
    background: transparent;
}

/* ── 标签 ───────────────────────────────────────── */
QLabel {
    color: #ffffff;
    background: transparent;
}

/* ── 工具提示 ───────────────────────────────────── */
QToolTip {
    background: rgba(25, 28, 36, 0.97);
    color: #ccc;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}

/* ── 进度条 ─────────────────────────────────────── */
QProgressBar {
    background: rgba(255,255,255,0.04);
    border: none;
    border-radius: 2px;
    height: 4px;
    color: transparent;
}
QProgressBar::chunk {
    background: #2AABEE;
    border-radius: 2px;
}

/* ── 分组框 ─────────────────────────────────────── */
QGroupBox {
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 12px 10px;
    font-weight: 600;
    color: #A2ACB9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}

/* ── 复选框 / 单选 ──────────────────────────────── */
QCheckBox {
    spacing: 6px;
    color: #ffffff;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid rgba(255,255,255,0.12);
}
QCheckBox::indicator:checked {
    background: #2AABEE;
    border-color: #2AABEE;
}
QCheckBox::indicator:hover {
    border-color: rgba(255,255,255,0.25);
}

QRadioButton {
    spacing: 6px;
    color: #ffffff;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid rgba(255,255,255,0.12);
}
QRadioButton::indicator:checked {
    background: #2AABEE;
    border-color: #2AABEE;
}
"""

THEMES = {"dark": DARK_THEME}


def get_theme(name: str = "dark") -> str:
    return DARK_THEME


def set_smooth_scroll(scroll_area: QScrollArea):
    """为 QScrollArea 启用丝滑滚动 + 触控板式拖拽"""
    scroll_area.verticalScrollBar().setSingleStep(0)
    # 触控板/鼠标拖拽的惯性滚动
    QScroller.grabGesture(
        scroll_area.viewport() if scroll_area.widget() else scroll_area,
        QScroller.ScrollerGestureType.LeftMouseButtonGesture,
    )
    # 滚轮平滑动画
    filter_ = _SmoothWheelFilter(scroll_area)
    proxy = _EventFilterProxy(lambda obj, ev: filter_.handle_wheel(obj, ev) if ev.type() == QEvent.Type.Wheel else False)
    scroll_area.viewport().installEventFilter(proxy)
    # 保持引用防止 GC
    scroll_area._smooth_wheel_proxy = proxy
    scroll_area._smooth_wheel_filter = filter_


class _EventFilterProxy(QObject):
    """轻量 eventFilter 代理，避免每个 scroll area 建子类"""

    def __init__(self, handler):
        super().__init__()
        self._handler = handler

    def eventFilter(self, obj, event):
        return self._handler(obj, event)
