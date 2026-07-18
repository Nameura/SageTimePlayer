"""
订阅设置对话框

类似 v2rayN 风格：左侧订阅列表（卡片式），右侧编辑表单。
"""

import uuid
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from database import settings
from gui.confirm_dialog import ConfirmDialog
from gui.icons import load_icon
from gui.toggle import Toggle
from gui.toast import Toast

_STYLE = """
QDialog {
    background: #15151b;
}
QLabel {
    color: #ccc;
    font-size: 13px;
}
QLineEdit, QSpinBox, QComboBox {
    background: rgba(255,255,255,0.06);
    color: #ddd;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #648cff;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #888;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #1e1e24;
    color: #ddd;
    border: 1px solid rgba(255,255,255,0.08);
    selection-background-color: rgba(100,140,255,0.2);
}
QPushButton {
    background: rgba(255,255,255,0.06);
    color: #ddd;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background: rgba(255,255,255,0.10);
    border-color: rgba(100,140,255,0.3);
}
QPushButton:pressed {
    background: rgba(255,255,255,0.04);
}
QPushButton#btnPrimary {
    background: #648cff;
    color: #fff;
    border: none;
    font-weight: 500;
}
QPushButton#btnPrimary {
    background: #648cff;
    color: #fff;
    border: none;
    font-weight: 500;
}
QPushButton#btnPrimary:hover {
    background: #7aa0ff;
}
QPushButton#btnDanger {
    color: #ef4444;
}
QPushButton#btnDanger:hover {
    background: rgba(239,68,68,0.12);
}
QListWidget {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    border-radius: 6px;
    padding: 8px 12px;
    margin: 2px 0;
    color: #ccc;
}
QListWidget::item:selected {
    background: rgba(100,140,255,0.15);
    color: #fff;
}
QListWidget::item:hover {
    background: rgba(255,255,255,0.04);
}
"""


class SubscriptionDialog(QDialog):
    """订阅设置弹窗"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("订阅设置")
        self.setFixedSize(760, 520)
        self.setModal(True)
        self.setStyleSheet(_STYLE)

        self._subs: list[dict] = []
        self._selected_idx: int | None = None

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # 点击空白处取消焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("订阅管理")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #eee;")
        layout.addWidget(title)

        # ── 左右分栏: 左侧列表 + 右侧表单 ──────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左侧：订阅列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(8)

        left_label = QLabel("订阅分组")
        left_label.setStyleSheet("font-size: 12px; color: #888;")
        left_layout.addWidget(left_label)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list, stretch=1)

        list_btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("新增", objectName="btnPrimary")
        self._add_btn.clicked.connect(self._add)
        list_btn_bar.addWidget(self._add_btn)

        self._del_btn = QPushButton("删除", objectName="btnDanger")
        self._del_btn.clicked.connect(self._delete)
        list_btn_bar.addWidget(self._del_btn)

        list_btn_bar.addStretch()
        left_layout.addLayout(list_btn_bar)

        splitter.addWidget(left_widget)

        # 右侧：编辑表单
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(8)

        right_label = QLabel("订阅配置")
        right_label.setStyleSheet("font-size: 12px; color: #888;")
        right_layout.addWidget(right_label)

        form = QFormLayout()
        form.setSpacing(12)
        form.setContentsMargins(0, 8, 0, 0)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText("例如：主力订阅")
        form.addRow("别名", self._alias_edit)

        # 订阅地址 + 粘贴按钮
        url_row = QHBoxLayout()
        url_row.setSpacing(4)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://example.com/sub?token=xxx")
        url_row.addWidget(self._url_edit, stretch=1)
        self._paste_btn = QPushButton()
        self._paste_btn.setIcon(load_icon("paste"))
        self._paste_btn.setIconSize(QSize(16, 16))
        self._paste_btn.setFixedSize(32, 32)
        self._paste_btn.setToolTip("点击从剪贴板粘贴")
        self._paste_btn.clicked.connect(self._paste_url)
        url_row.addWidget(self._paste_btn)
        form.addRow("订阅地址", url_row)

        # 排序（序号越小越靠前）
        self._sort_spin = QSpinBox()
        self._sort_spin.setRange(1, 9999)
        self._sort_spin.setValue(1)
        form.addRow("排序", self._sort_spin)

        # 自动更新：滑块开关 + 分钟输入
        auto_row = QHBoxLayout()
        auto_row.setSpacing(8)
        self._auto_toggle = Toggle()
        self._auto_toggle.setToolTip("启用后按间隔自动刷新订阅")
        self._auto_toggle.toggled.connect(self._on_auto_toggle)
        auto_row.addWidget(self._auto_toggle)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 999)
        self._interval_spin.setValue(60)
        self._interval_spin.setSuffix(" 分钟")
        self._interval_spin.setEnabled(False)
        # 灰色样式
        self._interval_spin.setStyleSheet("""
            QSpinBox {
                background: rgba(255,255,255,0.04);
                color: #666;
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QSpinBox:enabled {
                background: rgba(255,255,255,0.06);
                color: #ddd;
                border-color: rgba(255,255,255,0.08);
            }
            QSpinBox:focus { border-color: #648cff; }
            QSpinBox::up-button, QSpinBox::down-button {
                border: none; width: 18px;
            }
        """)
        auto_row.addWidget(self._interval_spin)
        auto_row.addStretch()
        form.addRow("自动更新", auto_row)

        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("例如：香港节点、备用线路…")
        form.addRow("备注", self._note_edit)

        right_layout.addLayout(form)
        right_layout.addStretch()

        # 表单操作按钮
        form_btn_bar = QHBoxLayout()
        self._save_btn = QPushButton("保存", objectName="btnPrimary")
        self._save_btn.clicked.connect(self._save_current)
        form_btn_bar.addWidget(self._save_btn)

        self._revert_btn = QPushButton("重置")
        self._revert_btn.clicked.connect(self._revert)
        form_btn_bar.addWidget(self._revert_btn)
        form_btn_bar.addStretch()
        right_layout.addLayout(form_btn_bar)

        splitter.addWidget(right_widget)
        splitter.setSizes([280, 480])
        layout.addWidget(splitter, stretch=1)

        # ── 底部全局按钮 ────────────────────────────────
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()

        self._ok_btn = QPushButton("确定", objectName="btnPrimary")
        self._ok_btn.clicked.connect(self._save_all_and_close)
        bottom_bar.addWidget(self._ok_btn)

        self._close_btn = QPushButton("取消")
        self._close_btn.clicked.connect(self.reject)
        bottom_bar.addWidget(self._close_btn)

        layout.addLayout(bottom_bar)

        # 所有按钮加手指指针
        for btn in self.findChildren(QPushButton):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── 数据操作 ────────────────────────────────────────

    def _load_data(self):
        self._subs = settings.get("subscriptions") or []
        # 按 sort 排序
        self._subs.sort(key=lambda s: s.get("sort", 9999))
        self._refresh_list()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _refresh_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for s in self._subs:
            alias = s.get("alias", "未命名")
            note = s.get("note", "")
            sort_val = s.get("sort", 1)
            display = f"{sort_val}. {alias}" + (f"  — {note}" if note else "")
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, s.get("id", ""))
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._subs):
            self._clear_form()
            self._selected_idx = None
            return
        self._selected_idx = row
        s = self._subs[row]
        self._alias_edit.setText(s.get("alias", ""))
        self._url_edit.setText(s.get("url", ""))
        self._sort_spin.setValue(s.get("sort", 1))
        auto_update = s.get("auto_update", 0)
        if auto_update > 0:
            self._auto_toggle.set_checked(True)
            self._interval_spin.setValue(auto_update)
        else:
            self._auto_toggle.set_checked(False)
            self._interval_spin.setValue(60)
        self._note_edit.setText(s.get("note", ""))

    def _clear_form(self):
        self._alias_edit.clear()
        self._url_edit.clear()
        self._sort_spin.setValue(1)
        self._auto_toggle.set_checked(False)
        self._interval_spin.setValue(60)
        self._note_edit.clear()

    def mousePressEvent(self, event):
        """点击空白处取消所有输入框的焦点"""
        self.setFocus()
        self._clear_focus()
        super().mousePressEvent(event)

    def _clear_focus(self):
        """清除所有输入控件的焦点"""
        self._alias_edit.clearFocus()
        self._url_edit.clearFocus()
        self._sort_spin.clearFocus()
        self._interval_spin.clearFocus()
        self._note_edit.clearFocus()

    def _paste_url(self):
        from PySide6.QtGui import QGuiApplication
        clip = QGuiApplication.clipboard()
        text = clip.text()
        if text:
            self._url_edit.setText(text.strip())

    def _on_auto_toggle(self, checked: bool):
        self._interval_spin.setEnabled(checked)

    def _add(self):
        """新增一个订阅"""
        max_sort = max((s.get("sort", 0) for s in self._subs), default=0)
        entry = {
            # id生成随机 UUID v4
            "id": str(uuid.uuid4()),
            "alias": "新订阅",
            "url": "https://",
            "sort": max_sort + 1,
            "auto_update": 0,
            "last_updated": 0,
            "note": "",
        }
        self._subs.append(entry)
        self._subs.sort(key=lambda s: s.get("sort", 9999))
        self._refresh_list()
        # 找到新添加的条目
        for i, s in enumerate(self._subs):
            if s["id"] == entry["id"]:
                self._list.setCurrentRow(i)
                break
        self._alias_edit.selectAll()
        self._alias_edit.setFocus()

    def _delete(self):
        if self._selected_idx is None or self._selected_idx >= len(self._subs):
            return
        alias = self._subs[self._selected_idx].get("alias", "未命名")
        dlg = ConfirmDialog("确认删除", f'确定要删除订阅「{alias}」吗？\n该操作不可撤销。', self)
        if not dlg.exec():
            return
        self._subs.pop(self._selected_idx)
        self._selected_idx = None
        self._refresh_list()
        self._clear_form()
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _save_current(self):
        """保存当前编辑的条目"""
        if self._selected_idx is None or self._selected_idx >= len(self._subs):
            return
        s = self._subs[self._selected_idx]
        s["alias"] = self._alias_edit.text().strip() or "未命名"
        s["url"] = self._url_edit.text().strip()
        s["sort"] = self._sort_spin.value()
        s["auto_update"] = self._interval_spin.value() if self._auto_toggle.is_checked else 0
        s["note"] = self._note_edit.text().strip()
        self._subs.sort(key=lambda x: x.get("sort", 9999))
        self._refresh_list()
        # 重新选中之前编辑的条目
        for i, x in enumerate(self._subs):
            if x["id"] == s["id"]:
                self._list.setCurrentRow(i)
                break
        Toast.show_message("✅ 保存成功", "success", 1500, self)

    def _revert(self):
        """重置表单为当前选中条目的原始值"""
        if self._selected_idx is not None:
            self._on_select(self._selected_idx)
            Toast.show_message("🔄 重置成功", "info", 1500, self)

    def _save_all_and_close(self):
        # 先保存当前编辑的条目
        self._save_current()
        settings.set("subscriptions", self._subs)
        self.accept()
