"""
自定义确认弹窗，与整体暗色主题一致
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)


class ConfirmDialog(QDialog):
    """暗色主题确认弹窗"""

    _STYLE = """
QDialog#confirmDialog {
    background: #1e1e26;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
}
QLabel#confirmTitle {
    color: #eee;
    font-size: 15px;
    font-weight: 600;
}
QLabel#confirmBody {
    color: #aaa;
    font-size: 13px;
}
QPushButton {
    background: rgba(255,255,255,0.06);
    color: #ccc;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 8px 28px;
    font-size: 13px;
    min-width: 80px;
}
QPushButton:hover {
    background: rgba(255,255,255,0.10);
}
QPushButton:pressed {
    background: rgba(255,255,255,0.04);
}
QPushButton#btnDangerConfirm {
    background: #e34141;
    color: #fff;
    border: none;
    font-weight: 500;
}
QPushButton#btnDangerConfirm:hover {
    background: #c93535;
}
QPushButton#btnDangerConfirm:pressed {
    background: #b02a2a;
}
"""

    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setObjectName("confirmDialog")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(self._STYLE)
        self.setFixedSize(380, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(0)

        # 标题
        title_lbl = QLabel(title, objectName="confirmTitle")
        layout.addWidget(title_lbl)

        # 正文
        body_lbl = QLabel(body, objectName="confirmBody")
        body_lbl.setWordWrap(True)
        body_lbl.setContentsMargins(0, 12, 0, 0)
        layout.addWidget(body_lbl)

        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("确定删除", objectName="btnDangerConfirm")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)

        layout.addLayout(btn_row)

        # 让弹窗居中
        if parent and parent.window():
            pw = parent.window()
            pw.installEventFilter(self)
            cx = pw.x() + pw.width() // 2
            cy = pw.y() + pw.height() // 2
            self.move(cx - self.width() // 2, cy - self.height() // 2)
