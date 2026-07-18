"""
可点击跳转的进度条

QSlider 默认只有拖拽滑块才能跳转，点击空白处不会跳。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class ClickableSlider(QSlider):
    """点击任意位置跳转的进度条"""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove = self.style().subControlRect(
                QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self
            )
            handle = self.style().subControlRect(
                QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self
            )
            if groove.isValid() and groove.width() > 0:
                half = handle.width() // 2
                start = groove.x() + half
                end = groove.x() + groove.width() - half
                if end > start:
                    ratio = (event.position().toPoint().x() - start) / (end - start)
                    ratio = max(0.0, min(1.0, ratio))
                    val = int(ratio * (self.maximum() - self.minimum())) + self.minimum()
                    self.setValue(val)
                    self.sliderMoved.emit(val)
        super().mousePressEvent(event)
