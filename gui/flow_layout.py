"""
流式布局

自动根据容器宽度换行，类似 CSS flex-wrap。
用于视频封面的自适应网格。
"""

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QStyle


class FlowLayout(QLayout):
    """流式布局 - 子控件自动换行"""

    def __init__(self, parent=None, margin=12, spacing=12):
        super().__init__(parent)
        self._items = []
        self._margin = margin
        self._spacing = spacing

    def addItem(self, item):
        self._items.append(item)

    def batch_set_items(self, widgets: list, parent_already_set: bool = False):
        """批量替换所有子控件，只触发一次布局。"""
        parent_widget = self.parent()

        # 清空旧项
        for item in self._items[:]:
            if item.widget():
                item.widget().setParent(None)
        self._items.clear()

        # 批量添加
        from PySide6.QtWidgets import QWidgetItem
        for w in widgets:
            if not parent_already_set:
                w.setParent(parent_widget)
            w.setVisible(True)
            self._items.append(QWidgetItem(w))

        # 立即执行一次完整布局
        if parent_widget:
            self.setGeometry(parent_widget.rect())
            parent_widget.update()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return QSize(600, 400)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self._margin, 2 * self._margin)
        return size

    def _do_layout(self, rect: QRect, only_height: bool) -> int:
        x = rect.x() + self._margin
        y = rect.y() + self._margin
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > rect.right() and line_height > 0:
                x = rect.x() + self._margin
                y += line_height + self._spacing
                line_height = 0
            if not only_height:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())

        return y + line_height + self._margin - rect.y()
