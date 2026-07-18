"""
视频封面卡片组件

Hanime1 风格：封面图 + 左上角时长 + 右下角点赞率/播放量 + 标题 + 副标题。
悬停时显示浮层大卡片展示完整信息。
"""

from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QFontMetrics
from PySide6.QtWidgets import QFrame, QLabel, QTextBrowser, QVBoxLayout, QHBoxLayout, QWidget

from gui.icons import load_svg_pixmap


class CoverTooltip(QFrame):
    """鼠标悬停时弹出的视频详情浮层（果冻弹入，文本可全选复制）"""

    def __init__(self, title: str, subtitle: str, duration: str,
                 thump_up: str, video_count: str, card: "CoverCard",
                 parent=None):
        super().__init__(parent)
        self._card = card
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(340, 170)

        # 背景容器
        container = QFrame(self)
        container.setObjectName("tooltipContainer")
        container.setStyleSheet("""
            #tooltipContainer {
                background: rgba(25, 28, 36, 0.97);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                color: #ddd;
            }
        """)
        container.setGeometry(0, 0, 340, 170)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # 标题 + 副标题合并到一个 QTextBrowser（支持跨行全选复制）
        self._text_browser = QTextBrowser()
        self._text_browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                color: #fff;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        self._text_browser.setOpenExternalLinks(False)
        html_parts = [f'<div style="font-size:14px;font-weight:600;color:#fff;">{title}</div>']
        if subtitle:
            html_parts.append(f'<div style="font-size:12px;font-weight:400;color:#999;margin-top:4px;">{subtitle}</div>')
        self._text_browser.setHtml("\n".join(html_parts))
        layout.addWidget(self._text_browser, stretch=1)

        # 底部信息行（SVG 图标）
        icon_s = 14
        info_texts = []
        if duration:
            info_texts.append(("duration", "#ffffff", duration))
        if thump_up:
            info_texts.append(("thump_up", "#ff6b9d", thump_up))
        if video_count:
            info_texts.append(("video_count", "#ffffff", video_count))

        if info_texts:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(12)
            for icon_name, color, val in info_texts:
                pix = load_svg_pixmap(icon_name, color, icon_s)
                icon_lbl = QLabel()
                icon_lbl.setPixmap(pix)
                icon_lbl.setFixedSize(icon_s + 2, icon_s)
                rl.addWidget(icon_lbl)
                val_lbl = QLabel(val)
                val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                val_lbl.setStyleSheet("font-size: 12px; color: #ccc;")
                rl.addWidget(val_lbl)
            rl.addStretch()
            layout.addWidget(row)

        self._target_pos = QPoint(0, 0)

    def show_at(self, global_pos: QPoint, card_size):
        """定位并播放弹入动画（大幅果冻效果）"""
        x = global_pos.x() + card_size.width() + 8
        y = global_pos.y() - 5
        screen = self.screen()
        if screen:
            sg = screen.availableGeometry()
            if x + self.width() > sg.right():
                x = global_pos.x() - self.width() - 8
            if y + self.height() > sg.bottom():
                y = sg.bottom() - self.height()
        self._target_pos = QPoint(x, y)

        # 从目标位置下方 30px 弹起
        start_pos = QPoint(self._target_pos.x(), self._target_pos.y() + 30)
        self.move(start_pos)
        self.setWindowOpacity(0.0)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # OutBack 加大过冲量 → 更 Q 弹
        curve = QEasingCurve(QEasingCurve.Type.OutBack)
        curve.setAmplitude(2.0)
        self._slide_in = QPropertyAnimation(self, b"pos")
        self._slide_in.setDuration(300)
        self._slide_in.setStartValue(start_pos)
        self._slide_in.setEndValue(self._target_pos)
        self._slide_in.setEasingCurve(curve)

        self._fade_in.start()
        self._slide_in.start()
        self.show()

    def enterEvent(self, event):
        if self._card:
            self._card._cancel_hide_tooltip()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._card:
            self._card._hide_tooltip()
        super().leaveEvent(event)


class CoverCard(QFrame):
    """视频封面卡片"""

    clicked = Signal(int)  # 发射 sort_order

    def __init__(self, sort_order: int, title: str, cover_url: str,
                 duration: str = "", thump_up: str = "",
                 video_count: str = "", subtitle: str = "",
                 parent=None):
        super().__init__(parent)
        self._sort_order = sort_order
        self._title = title
        self._cover_url = cover_url
        self._duration = duration
        self._thump_up = thump_up
        self._video_count = video_count
        self._subtitle = subtitle

        self._cover_pixmap: QPixmap | None = None
        self._thumb_pixmap: QPixmap | None = None
        self._count_pixmap: QPixmap | None = None
        self._tooltip: CoverTooltip | None = None
        self._hide_tooltip_timer = QTimer(self)
        self._hide_tooltip_timer.setSingleShot(True)
        self._hide_tooltip_timer.setInterval(200)
        self._hide_tooltip_timer.timeout.connect(self._hide_tooltip_now)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)
        self._hover_timer.timeout.connect(self._show_tooltip)

        self.setMouseTracking(True)

        self.setObjectName("coverCard")
        self.setFixedSize(210, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()

        # ── 封面图区域（上半部分） ─────────────────────
        cover_rect = rect.adjusted(6, 6, -6, -70)

        if self._cover_pixmap and not self._cover_pixmap.isNull():
            scaled = self._cover_pixmap.scaled(
                cover_rect.width(), cover_rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - cover_rect.width()) // 2
            y = (scaled.height() - cover_rect.height()) // 2
            cropped = scaled.copy(x, y, cover_rect.width(), cover_rect.height())
            p.drawPixmap(cover_rect, cropped)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(40, 42, 50))
            p.drawRoundedRect(cover_rect, 6, 6)
            p.setPen(QColor("#555"))
            font_icon = QFont("Segoe UI", 24)
            p.setFont(font_icon)
            p.drawText(cover_rect, Qt.AlignmentFlag.AlignCenter, "▶")

        # ── 时长标签（左上角） ──────────────────────────
        if self._duration:
            font_dur = QFont("Segoe UI", 10)
            p.setFont(font_dur)
            fm = QFontMetrics(font_dur)
            dur_text = f" {self._duration} "
            dur_w = fm.horizontalAdvance(dur_text) + 12
            dur_h = 20
            dur_x = cover_rect.x() + 4
            dur_y = cover_rect.y() + 4
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(dur_x, dur_y, dur_w, dur_h, 4, 4)
            p.setPen(QColor("#fff"))
            p.drawText(dur_x, dur_y, dur_w, dur_h,
                       Qt.AlignmentFlag.AlignCenter, dur_text)

        # ── 点赞率 + 播放量（右下角，各自独立背景） ────
        icon_size = 14
        font_info = QFont("Segoe UI", 9)
        p.setFont(font_info)
        fm = QFontMetrics(font_info)
        badge_h = 20
        gap = 4
        margin_right = 4
        margin_bottom = 4

        # 从右往左排：播放量（右）→ 点赞（左）
        cx = cover_rect.right() - margin_right

        if self._video_count:
            if not self._count_pixmap:
                self._count_pixmap = load_svg_pixmap("video_count", "#ffffff", icon_size)
            v_text = self._video_count
            vw = fm.horizontalAdvance(v_text) + 12 + icon_size
            vx = cx - vw
            vy = cover_rect.bottom() - badge_h - margin_bottom
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(vx, vy, vw, badge_h, 4, 4)
            p.drawPixmap(vx + 4, vy + (badge_h - icon_size) // 2, self._count_pixmap)
            p.setPen(QColor("#fff"))
            p.setFont(font_info)
            p.drawText(vx + 4 + icon_size + 3, vy, vw - icon_size - 4 - 3, badge_h,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, v_text)
            cx = vx - gap

        if self._thump_up:
            if not self._thumb_pixmap:
                self._thumb_pixmap = load_svg_pixmap("thump_up", "#ff6b9d", icon_size)
            t_text = self._thump_up
            tw = fm.horizontalAdvance(t_text) + 12 + icon_size
            tx = cx - tw
            ty = cover_rect.bottom() - badge_h - margin_bottom
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(tx, ty, tw, badge_h, 4, 4)
            p.drawPixmap(tx + 4, ty + (badge_h - icon_size) // 2, self._thumb_pixmap)
            p.setPen(QColor("#fff"))
            p.setFont(font_info)
            p.drawText(tx + 4 + icon_size + 3, ty, tw - icon_size - 4 - 3, badge_h,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t_text)

        # ── 标题（封面下方） ────────────────────────────
        title_rect = rect.adjusted(8, rect.height() - 64, -8, -40)
        p.setPen(QColor("#ddd"))
        font_title = QFont("Segoe UI", 11, QFont.Weight.Medium)
        p.setFont(font_title)
        elided = p.fontMetrics().elidedText(self._title, Qt.TextElideMode.ElideRight, title_rect.width())
        p.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # ── 副标题（video_subtitle，左端对齐，字号更小） ──
        if self._subtitle:
            sub_rect = rect.adjusted(8, rect.height() - 36, -8, -18)
            p.setPen(QColor("#888"))
            font_sub = QFont("Segoe UI", 9)
            p.setFont(font_sub)
            sub_elided = p.fontMetrics().elidedText(self._subtitle, Qt.TextElideMode.ElideRight, sub_rect.width())
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub_elided)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._sort_order)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._hover_timer.start()
        self._hide_tooltip_timer.stop()  # 取消待执行的隐藏
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        # 延迟隐藏，给鼠标移动到浮层的时间
        if self._tooltip:
            self._hide_tooltip_timer.start()
        super().leaveEvent(event)

    def _show_tooltip(self):
        if self._tooltip:
            return
        self._tooltip = CoverTooltip(
            title=self._title,
            subtitle=self._subtitle,
            duration=self._duration,
            thump_up=self._thump_up,
            video_count=self._video_count,
            card=self,
            parent=self.window(),
        )
        global_pos = self.mapToGlobal(QPoint(0, 0))
        self._tooltip.show_at(global_pos, self.size())

    def _cancel_hide_tooltip(self):
        """鼠标进入浮层时调用，取消隐藏"""
        self._hide_tooltip_timer.stop()

    def _hide_tooltip(self):
        """鼠标离开卡片或浮层时调用，立即隐藏"""
        self._hide_tooltip_timer.stop()
        self._hide_tooltip_now()

    def _hide_tooltip_now(self):
        """实际执行隐藏"""
        if self._tooltip:
            self._tooltip.close()
            self._tooltip.deleteLater()
            self._tooltip = None

    def set_cover(self, pixmap: QPixmap):
        self._cover_pixmap = pixmap
        self.update()

    @property
    def sort_order(self) -> int:
        return self._sort_order
