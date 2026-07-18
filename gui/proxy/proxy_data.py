"""
节点数据管理（桥接 proxy/ 模块与 GUI）

封装订阅拉取、节点列表加载、节点选取等逻辑。
订阅数据从 settings.json 读取，不再硬编码。
"""

import subprocess

from path.paths import ROOT

from proxy.fetch_nodes import fetch_subscription, try_decode_base64, parse_proxies_from_yaml
from proxy.launch_v2ray import (
    MIXED_PORT, load_proxies, pick_core,
    save_and_launch, wait_ready, proxy_on, proxy_off,
)
from database import settings


class ProxyManager:
    """节点管理器：加载 / 刷新 / 启停"""

    def __init__(self):
        self._proxies: list[dict] = []
        self._process: subprocess.Popen | None = None
        self._active_index: int | None = None

    # ── 节点列表 ────────────────────────────────────────

    def load(self):
        """从本地文件加载节点列表"""
        try:
            self._proxies = load_proxies()
        except Exception:
            self._proxies = []

    def refresh_all(self) -> dict:
        """
        依次刷新所有订阅分组，跳过失败的分组（保留旧节点）。
        返回 {"ok": [成功别名列表], "fail": [失败别名列表]}
        """
        subs = settings.get("subscriptions") or []
        ok_list: list[str] = []
        fail_list: list[str] = []

        for s in subs:
            alias = s.get("alias", "").strip()
            url = s.get("url", "").strip()
            if not alias or not url:
                continue
            try:
                self.refresh(url, alias)
                ok_list.append(alias)
            except Exception:
                fail_list.append(alias)

        return {"ok": ok_list, "fail": fail_list}

    def refresh(self, sub_url: str, alias: str) -> list[dict]:
        """
        拉取指定订阅链接，标记别名，合并到本地。
        sub_url: 订阅地址
        alias:   订阅别名（用于过滤和显示）
        """
        raw = fetch_subscription(sub_url)
        decoded = try_decode_base64(raw)
        new_nodes = parse_proxies_from_yaml(decoded)
        for p in new_nodes:
            p["_sub_alias"] = alias

        # 合并：移除该订阅的旧节点，追加新节点
        existing = self.proxies
        kept = [p for p in existing if p.get("_sub_alias", "") != alias]
        self._proxies = kept + new_nodes
        self._save_proxies()
        return self._proxies

    def _save_proxies(self):
        """持久化 proxies 到本地文件"""
        from proxy.fetch_nodes import NODES_YAML, NODES_TXT
        import yaml
        NODES_YAML.write_text(
            yaml.dump({"proxies": self._proxies}, allow_unicode=True),
            encoding="utf-8",
        )
        NODES_TXT.write_text(
            "\n".join(p.get("name", "?") for p in self._proxies),
            encoding="utf-8",
        )

    @property
    def proxies(self) -> list[dict]:
        if not self._proxies:
            self.load()
        return self._proxies

    @property
    def count(self) -> int:
        return len(self.proxies)

    def get_node(self, index: int) -> dict | None:
        proxies = self.proxies
        if 0 <= index < len(proxies):
            return proxies[index]
        return None

    # ── 核心 / 协议信息 ─────────────────────────────────

    def node_core(self, index: int) -> str:
        node = self.get_node(index)
        if not node:
            return "?"
        core, _ = pick_core(node)
        return core

    def node_protocol(self, index: int) -> str:
        node = self.get_node(index)
        return node.get("type", "?") if node else "?"

    # ── 代理启停 ────────────────────────────────────────

    def start(self, index: int) -> str:
        node = self.get_node(index)
        if not node:
            return "无效节点"
        if self._process and self._process.poll() is None:
            self.stop()
        try:
            self._process = save_and_launch(node)
            if wait_ready(self._process):
                proxy_on()
                self._active_index = index
                settings.set("last_node_id", index)
                settings.set("last_node_name", node.get("name", ""))
                return f"已连接 {node.get('name', '?')}"
            else:
                self._process = None
                return "启动超时"
        except FileNotFoundError as e:
            return f"缺少核心文件: {e}"
        except Exception as e:
            return f"启动失败: {e}"

    def stop(self):
        if self._process:
            proxy_off()
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._active_index = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def active_index(self) -> int | None:
        return self._active_index

    @property
    def active_node(self) -> dict | None:
        if self._active_index is not None:
            return self.get_node(self._active_index)
        return None
