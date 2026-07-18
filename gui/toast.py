"""
Element Plus 风格的 Toast 消息提示

浮动在窗口顶部中央，自动消失，支持 loading/success/error/info 类型。
加载提示带有旋转动画图标。
"""

from PySide6.QtCore import QPropertyAnimation, QPoint, QEasingCurve, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from gui.spinner import Spinner


class Toast(QFrame):
    """浮动消息提示"""

    # 类型对应的颜色和图标
    _STYLES = {
        "loading": {"bg": "rgba(30, 32, 38, 0.95)", "border": "rgba(100, 140, 255, 0.4)"},
        "success": {"bg": "rgba(30, 38, 32, 0.95)", "border": "rgba(34, 197, 94, 0.4)", "icon": "●"},
        "error":   {"bg": "rgba(38, 30, 30, 0.95)", "border": "rgba(239, 68, 68, 0.4)", "icon": "●"},
        "info":    {"bg": "rgba(30, 32, 38, 0.95)", "border": "rgba(100, 140, 255, 0.3)", "icon": "●"},
    }

    _ACTIVE_TOASTS: list["Toast"] = []

    def __init__(self, text: str, type: str = "info", duration: int = 2000, parent=None):
        super().__init__(parent)
        self._type = type
        self._duration = duration
        self._spinner: Spinner | None = None
        style = self._STYLES.get(type, self._STYLES["info"])

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedHeight(44)

        # 容器（实现圆角+背景）
        container = QFrame(self)
        container.setObjectName("toastContainer")
        container.setStyleSheet(f"""
            #toastContainer {{
                background: {style["bg"]};
                border: 1px solid {style["border"]};
                border-radius: 10px;
            }}
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        if type == "loading":
            self._spinner = Spinner(size=16, color="#648cff", parent=self)
            layout.addWidget(self._spinner)
            self._spinner.start()
        else:
            self._icon_label = QLabel(style["icon"])
            self._icon_label.setStyleSheet("font-size: 14px; color: #648cff; background: transparent;")
            layout.addWidget(self._icon_label)

        self._text_label = QLabel(text)
        self._text_label.setStyleSheet("color: #ddd; font-size: 13px; background: transparent;")
        layout.addWidget(self._text_label)

        # 整体布局（容器居中）
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self.adjustSize()
        self._reposition()

        # 入场动画
        self._anim_in = QPropertyAnimation(self, b"windowOpacity")
        self._anim_in.setDuration(300)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.OutCubic)

        # 出场动画
        self._anim_out = QPropertyAnimation(self, b"windowOpacity")
        self._anim_out.setDuration(300)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.InCubic)
        self._anim_out.finished.connect(self._on_fade_out_done)

        self._anim_in.start()

        # 自动消失定时器
        if duration > 0:
            QTimer.singleShot(duration, self._start_fade_out)

        self.show()
        self._ACTIVE_TOASTS.append(self)

    def _reposition(self):
        """定位到屏幕顶部居中（堆叠）"""
        try:
            if self.parent():
                parent_rect = self.parent().rect()
                x = parent_rect.center().x() - self.width() // 2
                y = 16 + len(self._ACTIVE_TOASTS) * 52
                self.move(self.parent().mapToGlobal(QPoint(x, y)))
            else:
                self.move(
                    self.screen().availableGeometry().center().x() - self.width() // 2,
                    16 + len(self._ACTIVE_TOASTS) * 52,
                )
        except RuntimeError:
            pass  # C++ 对象已销毁

    def _start_fade_out(self):
        self._anim_out.start()

    def _on_fade_out_done(self):
        try:
            if self._spinner:
                self._spinner.stop()
        except RuntimeError:
            pass
        if self in self._ACTIVE_TOASTS:
            self._ACTIVE_TOASTS.remove(self)
        # 重新排列剩余的 toast
        for i, t in enumerate(self._ACTIVE_TOASTS):
            t._reposition()
        try:
            self.close()
        except RuntimeError:
            pass

    @staticmethod
    def show_message(text: str, type: str = "info", duration: int = 2000, parent=None):
        """便捷静态方法"""
        return Toast(text, type, duration, parent)

    @staticmethod
    def show_loading(text: str, parent=None):
        """显示加载提示（不自动消失），先关闭旧加载提示"""
        # 关闭同类加载 toast，防止堆叠偏移
        for t in Toast._ACTIVE_TOASTS[:]:
            if t._type == "loading":
                t._on_fade_out_done()
        return Toast(text, "loading", 0, parent)

    @staticmethod
    def clear_all():
        for t in Toast._ACTIVE_TOASTS:
            t.close()
        Toast._ACTIVE_TOASTS.clear()
