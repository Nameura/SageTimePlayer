"""
配置管理模块

读写 database/settings.json，存储用户偏好。
提供简单的 get/set 接口，不依赖 SQLite。
"""

import json

from path.paths import DATA_DATABASE_DIR

# ── 路径 ────────────────────────────────────────────────
_SETTINGS_PATH = DATA_DATABASE_DIR / "settings.json"

# ── 默认配置 ────────────────────────────────────────────
_DEFAULTS = {
    "last_node_id": None,
    "last_node_name": "",
    "auto_start_proxy": True,
    "proxy_enabled": False,
    "first_time": True,
    "subscriptions": [],
    "_subscription_groups": [],
    "current_group": "全部",
    "last_cover_refresh": 0,
}


# ── 接口 ────────────────────────────────────────────────

def _load() -> dict:
    """从文件加载配置，合并默认值"""
    if not _SETTINGS_PATH.exists():
        return _DEFAULTS.copy() # 通过浅拷贝复制一份副本返回，这样不会污染全局的变量
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        # 合并默认值（新增的配置项自动补上）
        merged = _DEFAULTS.copy()
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return _DEFAULTS.copy()


def _save(data: dict):
    """写入配置到文件"""
    _SETTINGS_PATH.write_text(
        # 加indent=2后，生成的JSON会自动换行，并且每一层嵌套都会增加2个空格的缩进
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get(key: str):
    """读取配置项"""
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value):
    """设置配置项并持久化"""
    data = _load()
    data[key] = value
    _save(data)


def get_all() -> dict:
    """获取全部配置"""
    return _load()


def reset():
    """重置为默认值"""
    _save(_DEFAULTS.copy())
