"""
节点卡片组件

Clash 风格，显示协议/地区/延迟/流量等。
"""

import re
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# 国旗 emoji → 国家代码（更可靠）
_FLAG_MAP = {
    "🇯🇵": ("JP", "日本"),
    "🇸🇬": ("SG", "新加坡"),
    "🇭🇰": ("HK", "香港"),
    "🇰🇷": ("KR", "韩国"),
    "🇺🇸": ("US", "美国"),
    "🇹🇼": ("TW", "台湾"),
    "🇬🇧": ("GB", "英国"),
    "🇩🇪": ("DE", "德国"),
    "🇫🇷": ("FR", "法国"),
    "🇦🇺": ("AU", "澳洲"),
    "🇨🇦": ("CA", "加拿大"),
    "🇮🇳": ("IN", "印度"),
    "🇷🇺": ("RU", "俄罗斯"),
    "🇮🇩": ("ID", "印尼"),
    "🇲🇾": ("MY", "马来西亚"),
    "🇻🇳": ("VN", "越南"),
    "🇹🇭": ("TH", "泰国"),
    "🇳🇱": ("NL", "荷兰"),
    "🇸🇪": ("SE", "瑞典"),
    "🇫🇮": ("FI", "芬兰"),
    "🇨🇭": ("CH", "瑞士"),
    "🇮🇹": ("IT", "意大利"),
    "🇪🇸": ("ES", "西班牙"),
    "🇧🇷": ("BR", "巴西"),
    "🇦🇪": ("AE", "阿联酋"),
    "🇹🇷": ("TR", "土耳其"),
}

_CORE_COLORS = {
    "xray": "#2AABEE",
    "hysteria": "#9b59b6",
    "sing-box": "#e67e22",
}


def _parse_flag(name: str) -> tuple[str, str, str]:
    """从节点名提取国旗、国家代码和地区名"""
    for emoji, (code, region) in _FLAG_MAP.items():
        if emoji in name:
            return emoji, code, region
    return "🌐", "?", "未知"


def _core_label(core_name: str) -> str:
    m = {"xray": "X", "hysteria": "H", "sing-box": "S"}
    return m.get(core_name, "?")


class NodeCard(QFrame):
    """单个节点卡片"""

    clicked = Signal(int)  # 发射节点索引

    def __init__(self, index: int, name: str, core: str, protocol: str,
                 sub_alias: str = "", parent=None):
        super().__init__(parent)
        self._index = index
        self._name = name
        self._core = core
        self._protocol = protocol
        self._sub_alias = sub_alias
        self._flag_emoji, self._country_code, self._region = _parse_flag(name)

        self._active = False
        self._latency: float | None = None
        self._tested = False  # 是否已完成测速

        self.setObjectName("nodeCard")
        self.setFixedHeight(85)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def _update_style(self):
        border = (
            "1px solid rgba(42, 171, 238, 0.5)"
            if self._active
            else "1px solid rgba(255, 255, 255, 0.06)"
        )
        bg = (
            "rgba(42, 171, 238, 0.08)"
            if self._active
            else "rgba(255, 255, 255, 0.03)"
        )
        self.setStyleSheet(f"""
            #nodeCard {{
                background: {bg};
                border: {border};
                border-radius: 10px;
            }}
            #nodeCard:hover {{
                background: rgba(255, 255, 255, 0.06);
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        core_color = _CORE_COLORS.get(self._core, "#888")

        # ── 核心标签（左侧小圆角方块） ─────────────────
        core_x, core_y = 12, h // 2 - 11
        core_w, core_h = 22, 22
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(core_color))
        p.drawRoundedRect(core_x, core_y, core_w, core_h, 5, 5)
        p.setPen(QColor("#fff"))
        font_big = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(font_big)
        p.drawText(QRect(core_x, core_y, core_w, core_h),
                   Qt.AlignmentFlag.AlignCenter, _core_label(self._core))

        # ── 国旗 / 国家代码 ────────────────────────────
        flag_x = 44
        if self._country_code and self._country_code != "?":
            # 圆角蓝色代码标签
            code_w, code_h = 28, 22
            code_y = h // 2 - code_h // 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(42, 171, 238, 35))
            p.drawRoundedRect(flag_x, code_y, code_w, code_h, 6, 6)
            p.setPen(QColor("#6ab0f7"))
            font_code = QFont("Segoe UI", 9, QFont.Weight.Bold)
            p.setFont(font_code)
            p.drawText(QRect(flag_x, code_y, code_w, code_h),
                       Qt.AlignmentFlag.AlignCenter, self._country_code)
        else:
            font_flag = QFont("Segoe UI Emoji", 15)
            p.setFont(font_flag)
            p.setPen(QColor("#ccc"))
            p.drawText(QRect(flag_x, 0, 26, h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._flag_emoji)

        # ── 右侧信息 ──────────────────────────────────
        right_x = w - 12  # 右边缘

        # 延迟
        lat_width = 0
        if self._latency is not None:
            lat_color = "#4ade80" if self._latency < 300 else ("#fbbf24" if self._latency < 800 else "#f97373")
            p.setPen(QColor(lat_color))
            font_lat = QFont("Segoe UI", 11, QFont.Weight.Bold)
            p.setFont(font_lat)
            fm = QFontMetrics(font_lat)
            lat_text = f"{self._latency:.0f} ms"
            lat_width = fm.horizontalAdvance(lat_text) + 16
            p.drawText(QRect(right_x - lat_width, 14, lat_width, 22),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lat_text)
        elif self._tested:
            # 测过但不可达
            p.setPen(QColor("#666"))
            font_lat = QFont("Segoe UI", 10)
            p.setFont(font_lat)
            fm = QFontMetrics(font_lat)
            lat_text = "✗ 超时"
            lat_width = fm.horizontalAdvance(lat_text) + 16
            p.drawText(QRect(right_x - lat_width, 14, lat_width, 22),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lat_text)

        # 协议标签（右侧始终显示）
        proto_tag_w = 52
        proto_tag_x = right_x - proto_tag_w
        proto_tag_y = 46 if self._latency is not None else 32
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(proto_tag_x, proto_tag_y, proto_tag_w, 20, 6, 6)
        p.setPen(QColor("#999"))
        font_proto = QFont("Segoe UI", 9)
        p.setFont(font_proto)
        p.drawText(QRect(proto_tag_x, proto_tag_y, proto_tag_w, 20),
                   Qt.AlignmentFlag.AlignCenter, self._protocol)

        # ── 中间三行内容 ──────────────────────────────
        text_left = 80

        # 行1：节点名（加粗，自动省略）
        name_color = "#fff" if self._active else "#ddd"
        p.setPen(QColor(name_color))
        font_name = QFont("Segoe UI", 12, QFont.Weight.DemiBold)
        p.setFont(font_name)
        fm_name = QFontMetrics(font_name)
        name_max_w = w - text_left - proto_tag_w - 20 - lat_width
        display_name = fm_name.elidedText(self._name, Qt.TextElideMode.ElideRight, max(name_max_w, 40))
        p.drawText(QRect(text_left, 14, name_max_w, 24),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display_name)

        # 行2：地区
        p.setPen(QColor("#888"))
        font_mid = QFont("Segoe UI", 9)
        p.setFont(font_mid)
        p.drawText(QRect(text_left, 40, w - text_left - proto_tag_w - 20, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._region)

        # 行3：订阅来源
        if self._sub_alias:
            p.setPen(QColor(100, 140, 255, 140))
            font_sub = QFont("Segoe UI", 9)
            p.setFont(font_sub)
            p.drawText(QRect(text_left, 58, w - text_left - 12, 20),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"📦 {self._sub_alias}")

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
        super().mousePressEvent(event)

    # ── 属性 ────────────────────────────────────────────

    @property
    def index(self) -> int:
        return self._index

    def set_active(self, active: bool):
        self._active = active
        self._update_style()
        self.update()

    def set_latency(self, ms: float | None):
        self._latency = ms
        self._tested = True
        self.update()
        self.update()
