"""
带动画效果的滑块开关

仿 iOS/macOS 风格的滑动开关，带平滑过渡动画。
"""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class Toggle(QWidget):
    """滑块开关控件"""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._handle_pos = 2.0
        self.setFixedSize(42, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"handle_pos")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_handle_pos(self) -> float:
        return self._handle_pos

    def _set_handle_pos(self, pos: float):
        self._handle_pos = pos
        self.update()

    handle_pos = Property(float, _get_handle_pos, _set_handle_pos)

    @property
    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool):
        self._checked = checked
        target = 20.0 if checked else 2.0
        self._anim.stop()
        self._anim.setStartValue(self._handle_pos)
        self._anim.setEndValue(target)
        self._anim.start()
        self.toggled.emit(checked)

    def toggle(self):
        self.set_checked(not self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h // 2
        progress = (self._handle_pos - 2.0) / 18.0  # 0.0 ~ 1.0

        # 背景轨道 - 根据滑块位置渐变过渡
        r = int(60 + (100 - 60) * progress)
        g = int(62 + (140 - 62) * progress)
        b = int(70 + (255 - 70) * progress)
        bg = QColor(r, g, b)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # 滑块圆点
        dot_r = radius - 3
        dot_x = int(self._handle_pos)
        dot_y = (h - dot_r * 2) // 2
        p.setBrush(QColor("#fff"))
        p.drawEllipse(dot_x, dot_y, dot_r * 2, dot_r * 2)

        p.end()
