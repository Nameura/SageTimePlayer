"""
订阅节点获取工具

从订阅链接拉取节点信息，解码并存储为多种格式，
供 launch_v2ray.py（Xray/hysteria2/sing-box 启动器）使用。

输出文件（均在 proxy/ 目录下）:
  raw_subscription.txt  - 订阅源返回的原始内容（解码后的完整 Clash 配置）
  nodes.yaml            - 仅包含 proxies 列表，供代码解析
  nodes.txt             - 纯文本节点名列表，每行一个（便于快速查看）

用法（独立运行）:
  python proxy/fetch_nodes.py <订阅链接>
  或不传参，手动输入链接
"""

import base64
import sys
import warnings
from pathlib import Path

import requests
import yaml

warnings.filterwarnings("ignore",
    category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

from path.paths import DATA_PROXY_DIR

RAW_FILE = DATA_PROXY_DIR / "raw_subscription.txt"
NODES_YAML = DATA_PROXY_DIR / "nodes.yaml"
NODES_TXT = DATA_PROXY_DIR / "nodes.txt"

# 注意：SUB_URL 不再硬编码！
# GUI 通过 ProxyManager.refresh(url, alias) 传入订阅链接。
# 下面的 fetch_and_save 仅供手动/独立使用。


# ── 核心函数 ──────────────────────────────────────────────

# Python 类型注解（Type Hint），3.5+ 引入的语法，相当于给代码加"标注"，帮助人和工具理解数据类型
# 相当于这个函数：收一个字符串，返回一个字符串
def fetch_subscription(url: str) -> str:
    """从订阅链接拉取原始数据（字符串）。"""
    headers = {
        "User-Agent": "Clash/Meta",
        "Accept": "*/*",
    }
    resp = requests.get(url, headers=headers, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.text


def try_decode_base64(text: str) -> str:
    """如果内容疑似 Base64 编码，则解码；否则原样返回。"""
    text = text.strip()
    if not text:
        return ""

    # 已经是明文 YAML，无需解码
    if text.startswith("proxies:") or text.startswith("mixed-port:"):
        return text

    try:
        decoded = base64.b64decode(text.encode("utf-8"), validate=True).decode("utf-8")
        if decoded and decoded != text:
            return decoded
    except Exception:
        pass

    return text


def parse_proxies_from_yaml(text: str) -> list[dict]:
    """从完整的 Mihomo YAML 配置中提取 proxies 列表。"""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("订阅内容解析后不是合法的字典结构")
    proxies = data.get("proxies", [])
    if not isinstance(proxies, list):
        raise ValueError("订阅内容中 proxies 字段不是列表")
    return proxies


def get_node_names(proxies: list[dict]) -> list[str]:
    """从 proxies 列表中提取节点名。"""
    return [p.get("name", f"proxy-{i}") for i, p in enumerate(proxies)]


# ── 保存函数 ──────────────────────────────────────────────


def save_raw_subscription(text: str) -> Path:
    """保存订阅原始内容。"""
    RAW_FILE.write_text(text, encoding="utf-8")
    print(f"  ✅ 原始订阅: {RAW_FILE}")
    return RAW_FILE


def save_nodes_yaml(proxies: list[dict]) -> Path:
    """保存节点配置（仅 proxies 列表），供 Mihomo 配置合并使用。"""
    data = {"proxies": proxies}
    NODES_YAML.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"  ✅ 节点配置: {NODES_YAML}  ({len(proxies)} 个节点)")
    return NODES_YAML


def save_nodes_txt(names: list[str]) -> Path:
    """保存纯文本节点名称列表。"""
    NODES_TXT.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"  ✅ 节点列表 (文本): {NODES_TXT}")
    return NODES_TXT


# ── 一键执行 ──────────────────────────────────────────────
# 仅供开发调试使用，实际上只用了两个保存代理节点的入口

def fetch_and_save(sub_url: str | None = None) -> dict:
    """
    完整流程：拉取 → 解码 → 解析 → 保存。

    参数:
        sub_url: 订阅链接，为 None 时提示输入

    返回:
        { "raw_text": str, "proxies": list[dict], "names": list[str] }
    """
    if not sub_url:
        sub_url = input("请输入订阅链接: ").strip()
        if not sub_url:
            print("未提供订阅链接")
            return {"raw_text": "", "proxies": [], "names": []}

    print(" 正在拉取订阅...")
    raw_text = fetch_subscription(sub_url)

    print(" 正在解码...")
    decoded_text = try_decode_base64(raw_text)

    print(" 正在解析节点...")
    proxies = parse_proxies_from_yaml(decoded_text)
    names = get_node_names(proxies)

    print(f"\n 共获取 {len(proxies)} 个节点（含信息条目）\n")

    print(" 正在保存文件...")
    DATA_PROXY_DIR.mkdir(parents=True, exist_ok=True)
    save_raw_subscription(decoded_text)
    save_nodes_yaml(proxies)
    save_nodes_txt(names)

    print("\n 完成！")

    return {
        "raw_text": decoded_text,
        "proxies": proxies,
        "names": names,
    }


# ── 入口 ──────────────────────────────────────────────────


def main():
    fetch_and_save()


if __name__ == "__main__":
    main()
