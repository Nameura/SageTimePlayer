"""
旋转加载动画控件（SVG Spinner）

一个不断旋转的环形加载指示器，通过 QTimer + QPainter 实现。
"""

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class Spinner(QWidget):
    """旋转加载动画环"""

    def __init__(self, size: int = 18, color: str = "#648cff", parent=None):
        super().__init__(parent)
        self._angle = 0
        self._color = QColor(color)
        self._thickness = 2.5
        self.setFixedSize(size, size)

        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33fps，更流畅
        self._timer.timeout.connect(self._rotate)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _rotate(self):
        self._angle = (self._angle + 12) % 360  # 每步 12° 配合 30ms = 400°/s
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = self._thickness + 1
        rect = self.rect().adjusted(margin, margin, -margin, -margin)

        # 背景弧（半透明）
        pen = QPen(QColor(self._color.red(), self._color.green(), self._color.blue(), 40), self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # 前景弧（旋转）
        pen = QPen(self._color, self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        start_angle = self._angle * 16
        span_angle = 240 * 16  # 240° 弧长，看起来更动感
        painter.drawArc(rect, start_angle, span_angle)

        painter.end()
