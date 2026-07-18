"""
libmpv-2.dll 自动下载脚本

从 BtbN/mpv-winbuild 官方构建中下载 libmpv-2.dll 到 assets/tools/ 目录。
首次克隆项目后运行一次即可。

用法:
    python scripts/download_mpv.py
"""

import os
import sys
import requests
import json
import io
import tempfile
import shutil
from pathlib import Path

# ── 目标路径 ──────────────────────────────────────────
DLL_DIR = Path(__file__).resolve().parent.parent / "assets" / "tools"
DLL_PATH = DLL_DIR / "libmpv-2.dll"

# ── 下载源 ────────────────────────────────────────────
GITHUB_API = "https://api.github.com/repos/BtbN/mpv-winbuild/releases/latest"


def get_download_url() -> str | None:
    """从 BtbN/mpv-winbuild 最新 release 中找到 mpv-dev-x86_64-*.7z 的下载地址"""
    resp = requests.get(GITHUB_API, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    for asset in data.get("assets", []):
        name: str = asset["name"]
        if name.startswith("mpv-dev-x86_64-") and name.endswith(".7z"):
            return asset["browser_download_url"]
    return None


def extract_dll_from_7z(archive_path: Path, target_path: Path) -> bool:
    """从 7z 压缩包中提取 libmpv-2.dll"""
    # 优先用 py7zr
    try:
        import py7zr
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            # 列出所有文件，找到 libmpv-2.dll
            for name in z.getnames():
                if name.endswith("libmpv-2.dll"):
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    z.extract(target_path.parent, targets=[name])
                    extracted = target_path.parent / name
                    if extracted != target_path:
                        shutil.move(str(extracted), str(target_path))
                    return True
        return False
    except ImportError:
        pass

    # 备用：用系统 7z.exe
    import subprocess
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["7z", "e", str(archive_path), "-o" + str(tempfile.gettempdir()),
             "libmpv-2.dll", "-y"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            src = Path(tempfile.gettempdir()) / "libmpv-2.dll"
            if src.exists():
                shutil.move(str(src), str(target_path))
                return True
    except Exception:
        pass

    return False


def download_and_extract(url: str) -> bool:
    """下载 7z 并提取 libmpv-2.dll"""
    print(f"  下载: {url}")
    print("  文件较大 (~50MB)，请耐心等待...")

    with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            resp = requests.get(url, stream=True, timeout=300)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r    进度: {pct}% ({downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB)", end="")
            print()

            print("  正在解压...")
            if extract_dll_from_7z(tmp_path, DLL_PATH):
                size = DLL_PATH.stat().st_size
                print(f"  ✅ 已下载到: {DLL_PATH} ({size / 1024 / 1024:.1f} MB)")
                return True
            else:
                print("  ❌ 解压失败")
                return False

        finally:
            tmp.close()
            if tmp_path.exists():
                tmp_path.unlink()


def manual_instructions():
    """显示手动下载指引"""
    print()
    print("=" * 60)
    print("  自动下载失败，请手动下载 libmpv-2.dll：")
    print()
    print("  1. 打开: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/")
    print("  2. 下载最新版本的 .7z 文件")
    print("  3. 解压得到 libmpv-2.dll")
    print(f"  4. 复制到: {DLL_DIR}")
    print()
    print("  或使用 BtbN 的 GitHub 构建：")
    print("  https://github.com/BtbN/mpv-winbuild/releases")
    print("=" * 60)


def main():
    print("📦 libmpv-2.dll 下载工具")
    print("-" * 40)

    # 检查是否已存在
    if DLL_PATH.exists():
        size = DLL_PATH.stat().st_size
        print(f"  ✅ 已存在: {DLL_PATH} ({size / 1024 / 1024:.1f} MB)")
        return

    # 尝试自动下载
    DLL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        print("  正在获取最新版本信息...")
        url = get_download_url()
        if url:
            if download_and_extract(url):
                return
        else:
            print("  ❌ 未找到合适的下载文件")
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")

    manual_instructions()
    sys.exit(1)


if __name__ == "__main__":
    main()
