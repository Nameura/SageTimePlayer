"""
代理管理页面

流程：
  订阅设置 → 保存到 settings.json → 代理页面读取订阅列表 →
  显示分组芯片 → 点击芯片 → 刷新该订阅 → 展示对应节点
"""

import threading
import time
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QFrame,
)

from gui.proxy.node_card import NodeCard
from gui.proxy.proxy_data import ProxyManager
from gui.themes import set_smooth_scroll
from gui.toast import Toast
from database import settings


class ChipTooltip(QFrame):
    """订阅分组芯片的悬浮详情弹窗"""

    def __init__(self, alias: str, note: str, auto_update: int, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(220, 110)

        container = QFrame(self)
        container.setObjectName("chipTipContainer")
        container.setStyleSheet("""
            #chipTipContainer {
                background: rgba(25, 28, 36, 0.97);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }
            QLabel { background: transparent; color: #ccc; font-size: 12px; }
        """)
        container.setGeometry(0, 0, 220, 110)

        vl = QVBoxLayout(container)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(6)

        title_lbl = QLabel(alias)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #648cff;")
        vl.addWidget(title_lbl)

        nl = QLabel(f"📝 备注：{note}")
        vl.addWidget(nl)

        status = "已开启" if auto_update > 0 else "未开启"
        sl = QLabel(f"🔄 自动更新：{status}")
        sl.setStyleSheet("color: #888;")
        vl.addWidget(sl)

        self._target_pos = QPoint(0, 0)

    def show_at(self, global_pos: QPoint, btn_height: int):
        """定位在芯片下方并弹入"""
        x = global_pos.x()
        y = global_pos.y() + btn_height + 6
        screen = self.screen()
        if screen:
            sg = screen.availableGeometry()
            if x + self.width() > sg.right():
                x = sg.right() - self.width() - 8
            if y + self.height() > sg.bottom():
                y = global_pos.y() - self.height() - 6
        self._target_pos = QPoint(x, y)

        start_pos = QPoint(x, y + 20)
        self.move(start_pos)
        self.setWindowOpacity(0.0)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(180)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._slide_in = QPropertyAnimation(self, b"pos")
        self._slide_in.setDuration(300)
        self._slide_in.setStartValue(start_pos)
        self._slide_in.setEndValue(self._target_pos)
        self._slide_in.setEasingCurve(QEasingCurve.Type.OutBack)
        curve = QEasingCurve(QEasingCurve.Type.OutBack)
        curve.setAmplitude(2.0)
        self._slide_in.setEasingCurve(curve)

        self._fade_in.start()
        self._slide_in.start()
        self.show()


class ProxyPage(QWidget):
    """代理管理页面"""

    status_changed = Signal(str, str)
    _connect_result = Signal(str)
    _refresh_done = Signal()
    _refresh_all_done = Signal(object)
    _refresh_error = Signal(str)
    _speed_progress = Signal(object)
    _speed_done = Signal(object)
    _auto_update_done = Signal()

    def __init__(self, proxy_manager: ProxyManager, parent=None):
        super().__init__(parent)
        self._pm = proxy_manager
        self._cards: list[NodeCard] = []
        self._toast = None
        self._last_node: int | None = None
        self._chip_tooltip: ChipTooltip | None = None
        self._chip_tooltip_timer = QTimer(self)
        self._chip_tooltip_timer.setSingleShot(True)
        self._chip_tooltip_timer.setInterval(500)
        self._chip_tooltip_timer.timeout.connect(self._show_chip_tooltip)
        self._chip_hover_btn: QPushButton | None = None

        self._connect_result.connect(self._on_connect_result)
        self._refresh_done.connect(self._on_refresh_done)
        self._refresh_all_done.connect(self._on_refresh_all_done)
        self._refresh_error.connect(self._on_refresh_error)
        self._speed_progress.connect(self._on_speed_progress)
        self._speed_done.connect(self._on_speed_test_done)
        self._auto_update_done.connect(self._on_auto_update_done)

        self._build_ui()
        self._load_nodes()
        QTimer.singleShot(200, self._auto_connect)

        # ── 订阅自动更新 ────────────────────────────────
        self._updating_subs = False
        self._auto_update_timer = QTimer(self)
        self._auto_update_timer.timeout.connect(self._check_auto_updates)
        self._auto_update_timer.start(60_000)  # 每分钟检查一次

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # 顶部操作栏
        top = QHBoxLayout()
        top.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索节点名称…")
        self._search.setFixedWidth(260)
        self._search.textChanged.connect(self._filter)
        top.addWidget(self._search)
        top.addStretch()

        self._sub_btn = QPushButton("📋 订阅设置")
        self._sub_btn.setFixedHeight(34)
        self._sub_btn.clicked.connect(self._open_subs)
        top.addWidget(self._sub_btn)

        self._refresh_btn = QPushButton("🔄 更新订阅")
        self._refresh_btn.setFixedHeight(34)
        self._refresh_btn.clicked.connect(self._refresh_current)
        top.addWidget(self._refresh_btn)

        self._speed_btn = QPushButton("⚡ 测速")
        self._speed_btn.setFixedHeight(34)
        self._speed_btn.clicked.connect(self._run_speed_test)
        top.addWidget(self._speed_btn)

        self._conn_btn = QPushButton("🔌 连接节点")
        self._conn_btn.setFixedHeight(34)
        self._conn_btn.setFixedWidth(120)
        self._conn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._conn_btn.clicked.connect(self._toggle_conn)
        top.addWidget(self._conn_btn)

        self._reset_btn = QPushButton("🗑 重置代理")
        self._reset_btn.setFixedHeight(34)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._reset_proxy)
        top.addWidget(self._reset_btn)
        layout.addLayout(top)

        # 订阅分组芯片行
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 6)
        lbl = QLabel("订阅分组:")
        lbl.setStyleSheet("color: #888; font-size: 12px;")
        row.addWidget(lbl)
        self._chip_bar = QHBoxLayout()
        self._chip_bar.setSpacing(6)
        row.addLayout(self._chip_bar)
        row.addStretch()
        layout.addLayout(row)

        # 统计行
        self._info = QLabel("加载中…")
        self._info.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self._info)

        # 节点卡片列表
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        ctn = QWidget()
        self._card_layout = QVBoxLayout(ctn)
        self._card_layout.setSpacing(6)
        self._card_layout.setContentsMargins(0, 0, 12, 0)
        sc.setWidget(ctn)
        layout.addWidget(sc, stretch=1)
        set_smooth_scroll(sc)

        # 所有按钮加手指指针
        for btn in self.findChildren(QPushButton):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── 节点加载 ───────────────────────────────────────

    def _load_nodes(self):
        """从 ProxyManager 加载节点并重建卡片"""
        self._pm.load()
        proxies = self._pm.proxies
        # 按订阅别名分组排序，保证同一订阅的节点连续展示
        proxies.sort(key=lambda p: p.get("_sub_alias", ""))
        for c in self._cards:
            self._card_layout.removeWidget(c)
            c.deleteLater()
        self._cards.clear()

        for i, p in enumerate(proxies):
            card = NodeCard(
                index=i,
                name=p.get("name", "?"),
                core=self._pm.node_core(i),
                protocol=p.get("type", "?"),
                sub_alias=p.get("_sub_alias", ""),
            )
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

        self._build_chips()
        self._filter()
        if self._pm.active_index is not None:
            self._highlight(self._pm.active_index)

    # ── 订阅分组芯片 ───────────────────────────────────

    def _build_chips(self):
        """从 settings 读取订阅列表，重建分组芯片（首个为「全部代理」）"""
        self._hide_chip_tooltip()
        self._chip_tooltip_timer.stop()
        for i in reversed(range(self._chip_bar.count())):
            item = self._chip_bar.takeAt(i)
            if item.widget():
                item.widget().deleteLater()

        subs = settings.get("subscriptions") or []
        current = settings.get("current_group") or ""

        # 如果 current_group 无效，默认全部代理
        if current and not any(s.get("alias") == current for s in subs):
            current = ""
            settings.set("current_group", current)

        # 全部代理芯片
        all_btn = QPushButton("全部代理")
        all_btn.setFixedHeight(26)
        all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        all_btn.setProperty("alias", "")
        active = (current == "")
        all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {"rgba(100,140,255,0.2)" if active else "rgba(255,255,255,0.06)"};
                color: {"#648cff" if active else "#aaa"};
                border: 1px solid {"rgba(100,140,255,0.3)" if active else "rgba(255,255,255,0.06)"};
                border-radius: 13px; padding: 2px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.10); color: #ddd; }}
        """)
        all_btn.clicked.connect(self._on_chip_click)
        self._chip_bar.addWidget(all_btn)

        for s in subs:
            alias = s.get("alias", "").strip()
            if not alias:
                continue
            btn = QPushButton(alias)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("alias", alias)
            btn.setProperty("sub_note", s.get("note", "").strip())
            btn.setProperty("sub_auto_update", s.get("auto_update", 0))
            btn.installEventFilter(self)
            active = (alias == current)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {"rgba(100,140,255,0.2)" if active else "rgba(255,255,255,0.06)"};
                    color: {"#648cff" if active else "#aaa"};
                    border: 1px solid {"rgba(100,140,255,0.3)" if active else "rgba(255,255,255,0.06)"};
                    border-radius: 13px; padding: 2px 14px; font-size: 12px;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.10); color: #ddd; }}
            """)
            btn.clicked.connect(self._on_chip_click)
            self._chip_bar.addWidget(btn)

    def eventFilter(self, obj, event):
        """监听芯片按钮的鼠标进入/离开"""
        if isinstance(obj, QPushButton) and obj.property("alias") is not None:
            if event.type() == QEvent.Type.Enter:
                self._chip_hover_btn = obj
                self._chip_tooltip_timer.start()
            elif event.type() == QEvent.Type.Leave:
                self._chip_tooltip_timer.stop()
                self._hide_chip_tooltip()
        return super().eventFilter(obj, event)

    def _show_chip_tooltip(self):
        btn = self._chip_hover_btn
        if not btn or not btn.isVisible():
            return
        # 确保按钮还没被删除
        try:
            alias = btn.property("alias") or ""
            note = btn.property("sub_note") or ""
            auto_update = btn.property("sub_auto_update") or 0
        except RuntimeError:
            return  # C++ 对象已销毁
        self._hide_chip_tooltip()
        self._chip_tooltip = ChipTooltip(alias, note, auto_update, self.window())
        gp = btn.mapToGlobal(QPoint(0, 0))
        self._chip_tooltip.show_at(gp, btn.height())

    def _hide_chip_tooltip(self):
        if self._chip_tooltip:
            try:
                self._chip_tooltip.close()
                self._chip_tooltip.deleteLater()
            except RuntimeError:
                pass
            self._chip_tooltip = None

    def _on_chip_click(self):
        btn = self.sender()
        if not btn:
            return
        alias = btn.property("alias") or ""
        settings.set("current_group", alias)
        self._build_chips()
        self._load_nodes()

    # ── 刷新 ───────────────────────────────────────────

    def _refresh_current(self):
        """刷新当前选中分组的订阅"""
        alias = settings.get("current_group") or ""
        subs = settings.get("subscriptions") or []

        # 全部代理 → 依次刷新所有订阅
        if not alias:
            self._refresh_btn.setEnabled(False)
            self._refresh_btn.setText("刷新中…")
            self.status_changed.emit("正在刷新所有订阅…", "#f59e0b")
            self._toast = Toast.show_loading("正在拉取最新订阅…", self.window())

            def task_all():
                try:
                    result = self._pm.refresh_all()
                    self._refresh_all_done.emit(result)
                except Exception as e:
                    self._refresh_error.emit(str(e))

            threading.Thread(target=task_all, daemon=True).start()
            return

        url = None
        for s in subs:
            if s.get("alias", "").strip() == alias:
                url = s.get("url", "").strip()
                break
        if not url:
            Toast.show_message("⚠ 请在订阅设置中添加订阅链接", "error", 3000, self.window())
            return

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("刷新中…")
        self.status_changed.emit(f"正在刷新 [{alias}]…", "#f59e0b")
        self._toast = Toast.show_loading("正在拉取最新订阅…", self.window())

        def task():
            try:
                self._pm.refresh(url, alias)
                self._refresh_done.emit()
            except Exception as e:
                self._refresh_error.emit(str(e))

        threading.Thread(target=task, daemon=True).start()

    def _on_refresh_done(self):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("🔄 更新订阅")
        self.status_changed.emit("订阅已更新", "#22c55e")
        if self._toast:
            self._toast.close()
            self._toast = None
        # 计算当前分组的节点数
        alias = settings.get("current_group") or ""
        cnt = sum(1 for p in self._pm.proxies if p.get("_sub_alias", "") == alias)
        Toast.show_message(
            f"更新成功，当前分组更新 {cnt} 个节点", "success", 2000, self.window()
        )
        self._load_nodes()

    def _on_refresh_all_done(self, result: dict):
        """全部订阅刷新完成"""
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("🔄 更新订阅")
        ok_list = result.get("ok", [])
        fail_list = result.get("fail", [])
        parts = []
        if ok_list:
            green_names = "、".join(f'<span style="color:#4ade80">{n}</span>' for n in ok_list)
            parts.append(f"更新成功：{green_names}")
        if fail_list:
            red_names = "、".join(f'<span style="color:#f97373">{n}</span>' for n in fail_list)
            parts.append(f"更新失败：{red_names}")
        msg = "<br>".join(parts) if parts else "无更新"
        self.status_changed.emit(
            f"全部订阅刷新完成",
            "#22c55e" if not fail_list else "#f59e0b",
        )
        if self._toast:
            self._toast.close()
            self._toast = None
        Toast.show_message(msg, "success" if not fail_list else "info", 3000, self.window())
        self._load_nodes()

    def _on_refresh_error(self, msg: str):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("🔄 更新订阅")
        self.status_changed.emit(f"更新失败: {msg}", "#ef4444")
        if self._toast:
            self._toast.close()
            self._toast = None
        Toast.show_message(f"刷新失败: {msg}\n请检查订阅链接是否正确", "error", 3000, self.window())

    # ── 订阅自动更新 ──────────────────────────────────

    def _check_auto_updates(self):
        """每分钟检查一次，自动更新到期的订阅"""
        if self._updating_subs:
            return
        subs = settings.get("subscriptions") or []
        now = time.time()
        need_refresh = []
        for s in subs:
            interval = s.get("auto_update", 0)
            if interval <= 0:
                continue
            url = s.get("url", "").strip()
            alias = s.get("alias", "").strip()
            if not url or not alias:
                continue
            last = s.get("last_updated", 0)
            if now - last >= interval * 60:
                need_refresh.append((url, alias))

        if not need_refresh:
            return

        self._updating_subs = True

        def task():
            for url, alias in need_refresh:
                try:
                    self._pm.refresh(url, alias)
                    # 更新 last_updated
                    subs = settings.get("subscriptions") or []
                    for s in subs:
                        if s.get("alias", "").strip() == alias:
                            s["last_updated"] = time.time()
                            break
                    settings.set("subscriptions", subs)
                except Exception:
                    pass
            self._auto_update_done.emit()

        threading.Thread(target=task, daemon=True).start()

    def _on_auto_update_done(self):
        """自动更新完成"""
        self._updating_subs = False
        self._load_nodes()

    # ── 搜索 & 过滤 ────────────────────────────────────

    def _filter(self):
        """按当前分组 + 搜索文字过滤节点"""
        text = self._search.text().lower().strip()
        alias = settings.get("current_group") or ""
        proxies = self._pm.proxies

        shown = 0
        for i, card in enumerate(self._cards):
            if i >= len(proxies):
                break
            name_ok = not text or text in proxies[i].get("name", "").lower()
            group_ok = not alias or proxies[i].get("_sub_alias", "") == alias
            vis = name_ok and group_ok
            card.setVisible(vis)
            if vis:
                shown += 1

        total = len(proxies)
        active = ""
        if self._pm.is_running and self._pm.active_node:
            active = self._pm.active_node.get("name", "")
        info = f"共 {total} 个节点 | 当前分组 {shown} 个"
        if active:
            info += f" | 已连接: {active}"
        self._info.setText(info)

    # ── 卡片点击 ───────────────────────────────────────

    def _on_card_clicked(self, idx: int):
        self._connect_to(idx)

    def _highlight(self, idx: int):
        for c in self._cards:
            c.set_active(c.index == idx)

    # ── 连接/断开 ──────────────────────────────────────

    def _toggle_conn(self):
        if self._conn_btn.text() == "🔌 断开连接":
            self._last_node = self._pm.active_index
            self._disconnect()
        else:
            idx = self._last_node if self._last_node is not None else self._pm.active_index
            if idx is None:
                for c in self._cards:
                    if c.isVisible():
                        idx = c.index
                        break
            if idx is not None:
                self._connect_to(idx)

    def _connect_to(self, idx: int):
        self._conn_btn.setEnabled(False)
        self._conn_btn.setText("开启中…")
        name = self._pm.get_node(idx).get("name", "?") if self._pm.get_node(idx) else "?"
        self.status_changed.emit(f"连接 {name}…", "#648cff")
        self._toast = Toast.show_loading(f"正在连接 {name}…", self.window())

        def task():
            msg = self._pm.start(idx)
            self._connect_result.emit(msg)

        threading.Thread(target=task, daemon=True).start()

    def _on_connect_result(self, msg: str):
        self._conn_btn.setEnabled(True)
        if "已连接" in msg:
            self._conn_btn.setText("🔌 断开连接")
            self._highlight(self._pm.active_index)
            self.status_changed.emit(msg, "#22c55e")
            settings.set("proxy_enabled", True)
            Toast.show_message("✅ " + msg, "success", 2000, self.window())
        else:
            self._conn_btn.setText("🔌 连接节点")
            self.status_changed.emit(msg, "#ef4444")
            Toast.show_message("❌ " + msg, "error", 3000, self.window())
        if self._toast:
            self._toast.close()
            self._toast = None
        self._filter()

    def _disconnect(self):
        self._pm.stop()
        self._conn_btn.setText("🔌 开启代理")
        self._highlight(-1)
        self.status_changed.emit("代理已断开", "#888")
        settings.set("proxy_enabled", False)
        Toast.show_message("代理已断开", "info", 2000, self.window())
        self._filter()

    def _reset_proxy(self):
        """重置系统代理（清除注册表），如已连接则断开"""
        from proxy.launch_v2ray import proxy_off
        proxy_off()
        if self._pm.is_running:
            self._pm.stop()
        self._conn_btn.setText("🔌 开启代理")
        self._highlight(-1)
        self.status_changed.emit("系统代理已重置", "#888")
        settings.set("proxy_enabled", False)
        Toast.show_message("系统代理已重置，请重新选择节点连接", "info", 3000, self.window())
        self._filter()

    # ── 订阅设置 ───────────────────────────────────────

    def _open_subs(self):
        from gui.proxy.subscription_dialog import SubscriptionDialog
        dlg = SubscriptionDialog(self.window())
        if dlg.exec():
            self._build_chips()
            self._filter()

    # ── 自动连接 ───────────────────────────────────────

    def _auto_connect(self):
        if settings.get("auto_start_proxy") and not settings.get("first_time"):
            node_id = settings.get("last_node_id")
            if node_id is not None and 0 <= node_id < len(self._pm.proxies):
                self._connect_to(node_id)
            elif settings.get("last_node_name"):
                for i, p in enumerate(self._pm.proxies):
                    if p.get("name", "") == settings.get("last_node_name"):
                        self._connect_to(i)
                        break

    # ── 测速 ───────────────────────────────────────────

    def _run_speed_test(self):
        # 只测当前分组的可见节点
        nodes = []
        for i, card in enumerate(self._cards):
            if card.isVisible() and i < len(self._pm.proxies):
                nodes.append(self._pm.proxies[i])
        if not nodes:
            Toast.show_message("⚠ 当前分组没有节点可测速", "error", 2000, self.window())
            return

        self._speed_btn.setEnabled(False)
        self._speed_btn.setText("⏳ 测速中…")
        self.status_changed.emit(f"正在测速 {len(nodes)} 个节点…", "#f59e0b")

        def task():
            from gui.proxy.speed_test import test_all_nodes

            def on_progress(done, total):
                self._speed_progress.emit((done, total))

            results = test_all_nodes(nodes, on_progress=on_progress)
            self._speed_done.emit(results)

        threading.Thread(target=task, daemon=True).start()

    def _on_speed_progress(self, data):
        done, total = data
        pct = int(done / total * 100) if total > 0 else 0
        self._speed_btn.setText(f"⏳ {pct}%")

    def _on_speed_test_done(self, results):
        self._speed_btn.setEnabled(True)
        self._speed_btn.setText("⚡ 测速")
        results = results or []
        valid = [r for r in results if r is not None]
        if not valid:
            self.status_changed.emit("测速完成，无可达节点", "#ef4444")
            Toast.show_message("⚠ 所有节点均不可达", "error", 3000, self.window())
            return
        avg = sum(valid) / len(valid)
        # 将延迟写回可见的节点卡片（可达或不可达都标）
        vis_idx = 0
        for card in self._cards:
            if card.isVisible() and vis_idx < len(results):
                card.set_latency(results[vis_idx])
                vis_idx += 1
        self.status_changed.emit(
            f"测速完成: {len(valid)}/{len(results)} 可达, 平均 {avg:.0f}ms", "#22c55e"
        )
        Toast.show_message(
            f"⚡ 测速完成: {len(valid)}/{len(results)} 可达, 平均 {avg:.0f}ms",
            "success", 3000, self.window(),
        )
