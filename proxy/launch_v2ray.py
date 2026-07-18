"""
全能代理启动器

根据节点协议自动选择核心：xray / hysteria / sing-box
支持订阅中所有节点类型。

用法：
  & ".venv\Scripts\python.exe" .\proxy\launch_v2ray.py
"""

import ctypes
import json
import re
import subprocess
import time
import winreg
from pathlib import Path

import requests


def _replace_flags(text: str) -> str:
    """替换国旗 emoji 为国家缩写（🇺🇸 → [US]、🇯🇵 → [JP]），并过滤其他无法编码的字符"""
    import re
    # 国旗 emoji 由 2 个雷鬼位字符组成（范围 0x1F1E6-0x1F1FF）
    def _replace(m):
        code_points = [ord(c) for c in m.group(0)]
        if len(code_points) >= 2:
            c1 = code_points[0] - 0x1F1E6
            c2 = code_points[1] - 0x1F1E6
            if 0 <= c1 < 26 and 0 <= c2 < 26:
                return f"[{chr(65 + c1)}{chr(65 + c2)}]"
        return "?"
    text = re.sub(r'[\U0001F1E6-\U0001F1FF]{2}', _replace, text)
    return text


def _safe_print(text: str):
    """安全打印：替换国旗 emoji 为缩写，过滤无法编码的字符"""
    text = _replace_flags(text)
    try:
        print(text)
    except UnicodeEncodeError:
        safe = text.encode("gbk", errors="replace").decode("gbk")
        print(safe)
import yaml

from path.paths import DATA_PROXY_DIR, ROOT

# ── 路径 ────────────────────────────────────────────────
# 代码 & 可执行文件路径（只读，打包进 exe）
V2RAY_DIR = ROOT / "proxy" / "v2ray"
XRAY_EXE = V2RAY_DIR / "xray" / "xray.exe"
HYSTERIA_EXE = V2RAY_DIR / "hysteria" / "hysteria-windows-amd64.exe"
HYSTERIA2_EXE = V2RAY_DIR / "hysteria" / "hysteria2.exe"
SING_BOX_EXE = V2RAY_DIR / "sing_box" / "sing-box.exe"
CONFIG_FILE = V2RAY_DIR / "config.json"

# 用户数据路径（运行时生成）
SUB_CONFIG = DATA_PROXY_DIR / "nodes.yaml"
MIXED_PORT = 10909

# ── 核心映射 ────────────────────────────────────────────
PROTOCOL_MAP = {
    "vless":       ("xray", XRAY_EXE),
    "vmess":       ("xray", XRAY_EXE),
    "trojan":      ("xray", XRAY_EXE),
    "shadowsocks": ("xray", XRAY_EXE),
    "ss":          ("xray", XRAY_EXE),
    "socks5":      ("xray", XRAY_EXE),
    "socks":       ("xray", XRAY_EXE),
    "http":        ("xray", XRAY_EXE),
    "hysteria2":   ("hysteria", HYSTERIA2_EXE),
    "hy2":         ("hysteria", HYSTERIA2_EXE),
    "hysteria":    ("hysteria", HYSTERIA_EXE),
}
FALLBACK_CORE = ("sing-box", SING_BOX_EXE)

# ── 订阅 ────────────────────────────────────────────────

def load_proxies() -> list[dict]:
    data = yaml.safe_load(SUB_CONFIG.read_text(encoding="utf-8"))
    return data.get("proxies", [])

def pick_core(proxy: dict) -> tuple[str, Path]:
    proto = proxy.get("type", "").lower()
    r = PROTOCOL_MAP.get(proto)
    if r and r[1].exists():
        return r
    if FALLBACK_CORE[1].exists():
        return FALLBACK_CORE
    return r if r else ("?", Path())

# ── Xray 配置 ────────────────────────────────────────────

def build_xray(proxy: dict) -> dict:
    p = proxy
    stream = {"network": p.get("network", "tcp")}
    if p.get("reality") or p.get("tls"):
        sn = p.get("servername") or p.get("sni", "")
        if p.get("reality"):
            stream["security"] = "reality"
            ro = p.get("reality-opts", {})
            stream["realitySettings"] = {
                "serverName": sn,
                "fingerprint": p.get("client-fingerprint", p.get("fingerprint", "chrome")),
                "publicKey": ro.get("public-key", ""),
                "shortId": ro.get("short-id", ""),
                "spiderX": ro.get("spider-x", ""),
            }
        else:
            stream["security"] = "tls"
            stream["tlsSettings"] = {"serverName": sn, "allowInsecure": p.get("skip-cert-verify", False)}
    if stream["network"] == "ws":
        ws = p.get("ws-opts", {})
        s = {}
        if ws.get("path"): s["path"] = ws["path"]
        if ws.get("headers"): s["headers"] = ws["headers"]
        stream["wsSettings"] = s

    proto = p["type"].lower()
    settings = {}
    if proto == "vless":
        settings = {"vnext": [{"address": p["server"], "port": int(p["port"]), "users": [{"id": p.get("uuid", ""), "flow": p.get("flow", ""), "encryption": "none"}]}]}
    elif proto == "vmess":
        settings = {"vnext": [{"address": p["server"], "port": int(p["port"]), "users": [{"id": p.get("uuid", ""), "security": p.get("cipher", "auto")}]}]}
    elif proto == "trojan":
        settings = {"servers": [{"address": p["server"], "port": int(p["port"]), "password": p.get("password", "")}]}
    elif proto in ("shadowsocks", "ss"):
        settings = {"servers": [{"address": p["server"], "port": int(p["port"]), "method": p.get("cipher", p.get("method", "aes-256-gcm")), "password": p.get("password", "")}]}

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {"tag": "http-in", "port": MIXED_PORT, "listen": "127.0.0.1", "protocol": "http"},
            {"tag": "socks-in", "port": MIXED_PORT + 1, "listen": "127.0.0.1", "protocol": "socks", "settings": {"udp": True}},
        ],
        "outbounds": [
            {"tag": "proxy", "protocol": proto, "settings": settings, "streamSettings": stream},
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
                {"type": "field", "domain": ["geosite:cn"], "outboundTag": "direct"},
                {"type": "field", "ip": ["geoip:cn"], "outboundTag": "direct"},
            ],
        },
    }

# ── Hysteria 配置 ────────────────────────────────────────

def build_hysteria(proxy: dict) -> dict:
    p = proxy
    cfg = {
        "server": f"{p['server']}:{p['port']}",
        "auth": (p.get("password") or p.get("auth") or "").replace("-", ""),
        "socks5": {"listen": f"127.0.0.1:{MIXED_PORT}"},
        "http": {"listen": f"127.0.0.1:{MIXED_PORT}"},
        "skipCertVerify": p.get("skip-cert-verify", True),
        "sni": p.get("sni") or p.get("servername", ""),
    }
    if p.get("ports"):
        cfg["hopInterval"] = 30
    return cfg

# ── Sing-box 配置 ────────────────────────────────────────

def build_singbox(proxy: dict) -> dict:
    p = proxy
    out = {"type": p["type"], "tag": "proxy", "server": p["server"], "server_port": int(p["port"])}
    for k in ("uuid", "password", "flow", "method", "cipher", "network", "encryption"):
        if p.get(k): out[k] = p[k]
    if p.get("tls") or p.get("type") in ("hysteria2", "hy2", "hysteria"):
        out["tls"] = {"enabled": True, "server_name": p.get("servername", "") or p.get("sni", ""), "insecure": p.get("skip-cert-verify", True)}
    return {
        "log": {"level": "warn"},
        "inbounds": [
            {"type": "http", "tag": "http-in", "listen": "127.0.0.1", "listen_port": MIXED_PORT},
            {"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": MIXED_PORT + 1},
        ],
        "outbounds": [out, {"type": "direct", "tag": "direct"}],
    }

# ── 启动 ────────────────────────────────────────────────

def save_and_launch(proxy: dict) -> subprocess.Popen:
    core_type, core_exe = pick_core(proxy)
    if not core_exe.exists():
        raise FileNotFoundError(f"找不到核心: {core_exe}")
    _safe_print(f"\n使用 {core_exe.name} 启动 [{proxy.get('name', '?')}]")

    if core_type == "xray":
        cfg = build_xray(proxy)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return subprocess.Popen([str(core_exe), "-c", str(CONFIG_FILE)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    elif core_type == "hysteria":
        cfg = build_hysteria(proxy)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return subprocess.Popen([str(core_exe), "client", "-c", str(CONFIG_FILE)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        cfg = build_singbox(proxy)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return subprocess.Popen([str(core_exe), "run", "-c", str(CONFIG_FILE)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)

# 轮询等待核心就绪
def wait_ready(proc: subprocess.Popen) -> bool:
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            _safe_print(f"启动失败:\n{out}")
            return False
        try:
            requests.get(f"http://127.0.0.1:{MIXED_PORT}", timeout=1)
            return True
        except requests.RequestException:
            time.sleep(0.3)
    return False

# ── 系统代理 ─────────────────────────────────────────────

REG = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

def proxy_on():
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 1)
    winreg.SetValueEx(k, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{MIXED_PORT}")
    winreg.CloseKey(k)
    ctypes.windll.Wininet.InternetSetOptionW(None, 39, None, 0)
    ctypes.windll.Wininet.InternetSetOptionW(None, 37, None, 0)
    print(f"系统代理已开启 → 127.0.0.1:{MIXED_PORT}")

def proxy_off():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(k)
        ctypes.windll.Wininet.InternetSetOptionW(None, 39, None, 0)
        ctypes.windll.Wininet.InternetSetOptionW(None, 37, None, 0)
    except Exception:
        pass

# ── 交互菜单 ─────────────────────────────────────────────

def main():
    if not SUB_CONFIG.exists():
        print("未找到订阅，请先运行 fetch_nodes.py")
        return

    proxies = load_proxies()
    process = None

    try:
        while True:
            labels = {"xray": "X", "hysteria": "H", "sing-box": "S"}
            print(f"\n{'='*45}")
            print(f"  共 {len(proxies)} 个节点")
            print(f"{'='*45}")
            for i, p in enumerate(proxies, 1):
                core, _ = pick_core(p)
                print(f"  {i:>2}. [{labels.get(core,'?')}] {p.get('name','?')}")
            print(f"{'='*45}")
            print(f"  0.  退出   对应核心: X=xray  H=hysteria  S=sing-box")
            print(f"{'='*45}")

            ch = input("\n请选择节点编号: ").strip()
            if ch == "0":
                break
            try:
                idx = int(ch) - 1
                if 0 <= idx < len(proxies):
                    sel = proxies[idx]
                    process = save_and_launch(sel)
                    if wait_ready(process):
                        print(f"代理已就绪！端口: {MIXED_PORT}")
                        proxy_on()
                        print("\n按 Enter 停止代理")
                        input()
                    else:
                        print("启动超时")
                    break
                else:
                    print("编号超出范围")
            except ValueError:
                print("请输入数字")
    finally:
        if process:
            print("\n正在停止...")
            proxy_off()
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
            print(" 已停止")

if __name__ == "__main__":
    main()
