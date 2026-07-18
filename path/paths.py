"""
路径中心模块

统一管理「项目代码路径」和「用户数据路径」的分离。
开发环境（有 .devmode 标记）数据存在项目目录，打包后存在 %APPDATA%。
所有其他文件只需从此模块导入路径，无需关心运行环境。
"""

import os
import sys
from pathlib import Path

# ── 项目根目录 ─────────────────────────────────────────
# 开发：项目目录 | 打包：sys._MEIPASS（即 _internal/ 目录）
if getattr(sys, 'frozen', False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent.parent

# ── 附加数据目录（--add-data 指定的文件） ─────────────
# 打包后这些文件在 _internal/ 下，开发时在项目根目录下
SCRAPY_CORE_DIR = ROOT / "scrapy_core"


def _detect_data_dir() -> Path:
    """判断当前是开发模式还是打包模式"""
    # 开发模式：项目根目录有 .devmode 标记文件
    if (ROOT / ".devmode").exists():
        return ROOT
    # 打包模式：使用 %APPDATA%
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "SageTimePlayer"
    # 兜底
    return ROOT


# ── 数据目录（用户数据的存放位置）────────────────────────
DATA_DIR = _detect_data_dir()

# ── 子目录快捷路径（按需在此扩展）────────────────────────
# 注意：仅在需要时创建目录，不要在此处提前创建所有目录
DATA_DATABASE_DIR = DATA_DIR / "database"
DATA_PROXY_DIR = DATA_DIR / "proxy"


def ensure_data_dirs():
    """确保数据目录结构存在（首次运行时创建）"""
    DATA_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROXY_DIR.mkdir(parents=True, exist_ok=True)
