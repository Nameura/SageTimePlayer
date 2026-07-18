"""
图标工具

从 assets/icons/ 加载 SVG 图标，返回 QIcon 或着色后的 QPixmap。
"""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer

_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def load_icon(name: str) -> QIcon:
    """加载 SVG 图标文件，返回 QIcon"""
    svg_path = _ICONS_DIR / f"{name}.svg"
    if svg_path.exists():
        return QIcon(str(svg_path))
    return QIcon()


def load_svg_pixmap(name: str, color: str, size: int = 16) -> QPixmap:
    """
    加载 SVG 图标并着色，返回指定大小的 QPixmap（4x 渲染后平滑缩小）。
    支持 stroke 和 fill 两种着色方式。
    """
    svg_path = _ICONS_DIR / f"{name}.svg"
    if not svg_path.exists():
        return QPixmap()

    svg_content = svg_path.read_text(encoding="utf-8")
    # 替换 currentColor 为指定颜色（Feather 等 stroke 图标）
    svg_content = svg_content.replace('currentColor', color)
    # 替换 fill="" 为指定颜色（部分图标用 fill）
    svg_content = svg_content.replace('fill=""', f'fill="{color}"')

    # 8x 渲染再平滑缩放
    hi_size = size * 8
    pixmap = QPixmap(hi_size, hi_size)
    pixmap.fill(QColor(0, 0, 0, 0))
    renderer = QSvgRenderer(svg_content.encode("utf-8"))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()

    return pixmap.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
