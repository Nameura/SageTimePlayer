"""
左侧导航侧边栏组件

现代简洁风格，图标+文字标签，支持切换页面。
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QColor, QFont
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout
from gui.icons import load_icon


# 自定义按钮类
class SidebarButton(QPushButton):
    """侧边栏单个导航按钮"""

    def __init__(self, icon_name: str, label: str, parent=None, compact=False):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label = label
        self._active = False
        self._compact = compact
        self.setCheckable(True)
        h = 44 if compact else 52
        self.setFixedSize(80, h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._style_normal())

    def _style_normal(self) -> str:
        return """
        QPushButton {
            background: transparent; /* 背景透明 */
            border: none;
            border-radius: 8px;
            color: #A2ACB9;
            font-size: 11px;
        }
        QPushButton:hover {
            background: rgba(42, 171, 238, 0.08);
            color: #ffffff;
        }
        QPushButton:checked {
            background: rgba(42, 171, 238, 0.12);
            color: #2AABEE;
        }
        """

    # 切换选中
    def set_active(self, active: bool):
        self._active = active
        self.setChecked(active)

    # 自绘按钮
    def paintEvent(self, event):
        super().paintEvent(event)
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPainter, QFont, QColor

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # SVG 图标
        icon = load_icon(self._icon_name)
        if not icon.isNull():
            top = 4 if self._compact else 6
            bottom = 22 if self._compact else 26
            mode = QIcon.Mode.Selected if self._active else QIcon.Mode.Normal
            icon.paint(p, self.rect().adjusted(29, top, -29, -bottom),
                       Qt.AlignmentFlag.AlignCenter, mode)

        # 标签文字（设置按钮右移留空间给文字）
        if self._label:
            font2 = QFont("Segoe UI", 9)
            p.setFont(font2)
            label_color = "#2AABEE" if self._active else "#A2ACB9"
            p.setPen(QColor(label_color))
            label_top = 30 if self._compact else 32
            p.drawText(self.rect().adjusted(0, label_top, 0, -2),
                       Qt.AlignmentFlag.AlignCenter, self._label)

        p.end()


# 侧边栏容器
class Sidebar(QFrame):
    """左侧导航侧边栏"""

    page_changed = Signal(int)  # 发射页面索引
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(88)
        self.setObjectName("sidebar")
        self.setStyleSheet("""
            #sidebar {
                background: rgba(14, 22, 33, 0.98);
                border-right: 1px solid rgba(255, 255, 255, 0.04);
            }
        """)

        # 创建垂直布局管理器，自动排列子控件
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 20, 4, 16)
        layout.setSpacing(2)

        # 顶部星标
        star = QLabel("★")
        star.setAlignment(Qt.AlignmentFlag.AlignCenter)
        star.setStyleSheet("font-size: 14px; color: #2AABEE; background: transparent;")
        layout.addWidget(star)
        layout.addSpacing(8)

        # 导航按钮组
        self._buttons = []
        self._nav_indices = {}  # 记录导航按钮的索引范围
        nav_items = [
            ("proxy", "代理"),     # 0
            ("video", "视频"),     # 1
        ]

        for i, (icon, label) in enumerate(nav_items):
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self._buttons.append(btn)

        layout.addStretch()

        # ── 底部按钮组 ──────────────────────────────────
        # 设置
        self._settings_btn = SidebarButton("settings", "设置", compact=True)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        self._buttons.append(self._settings_btn)
        layout.addWidget(self._settings_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 默认选中第一个
        if self._buttons:
            self._buttons[0].set_active(True)

    # 点击处理
    def _on_click(self, index: int):
        # 底部按钮不触发页面切换
        if index >= 2:
            return
        # 遍历所有按钮，只有被点击的那个设为激活，其余取消
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)

        # 发射 page_changed 信号，告诉外界："用户切换到第 index 页了"
        self.page_changed.emit(index)

    def set_active(self, index: int):
        """外部主动切换页面"""
        if 0 <= index < 2:
            self._buttons[index].set_active(True)
            self.page_changed.emit(index)
