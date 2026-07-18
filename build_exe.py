"""
SageTimePlayer 打包脚本
用法: python build_exe.py
"""
import PyInstaller.__main__
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── 打包前清理 ─────────────────────────────────────────
# 杀掉可能锁文件的残留进程
for exe_name in ["xray.exe", "hysteria-windows-amd64.exe", "hysteria2.exe", "sing-box.exe", "SageTimePlayer.exe"]:
    subprocess.run(["taskkill", "/f", "/im", exe_name], capture_output=True, text=True)
time.sleep(0.5)

# ── 前置检查 ──────────────────────────────────────────
DLL_PATH = ROOT / "assets" / "tools" / "libmpv-2.dll"
if not DLL_PATH.exists():
    print("❌ 缺少 libmpv-2.dll，请先运行: python scripts/download_mpv.py")
    sys.exit(1)

# ── 数据文件 ────────────────────────────────────────────

# 需要打包成文件夹的外部资源（--add-data 格式: src;dest）
# 分号前是源路径，分号后是目标 exe 内的相对路径
ADD_DATA = [
    # 代理核心
    (ROOT / "proxy" / "v2ray", "proxy/v2ray"),
    # libmpv
    (ROOT / "assets" / "tools" / "libmpv-2.dll", "assets/tools"),
    # SVG 图标
    (ROOT / "assets" / "icons", "assets/icons"),
    # Scrapy 爬虫配置和蜘蛛
    (ROOT / "scrapy_core" / "scrapy.cfg", "scrapy_core"),
    (ROOT / "scrapy_core" / "scrapy_spider", "scrapy_core/scrapy_spider"),
]

args = [
    "main.py",                          # 入口
    "--name=SageTimePlayer",            # exe 名称
    "--onedir",                         # 文件夹模式（推荐）
    "--windowed",                       # 无控制台窗口（发行版）
    "--clean",                          # 清理缓存
    "--noconfirm",                      # 覆盖输出不询问
    f"--distpath={ROOT / 'dist'}",     # 输出目录
    f"--workpath={ROOT / 'build_temp'}",
    # Scrapy 启动时需要读取这些包的版本元数据
    "--recursive-copy-metadata=scrapy",
]

for src, dest in ADD_DATA:
    args.append(f"--add-data={src}{';' if sys.platform == 'win32' else ':'}{dest}")

PyInstaller.__main__.run(args)

print("\n✅ 打包完成！输出目录: dist/SageTimePlayer/")
print("   双击 dist/SageTimePlayer/SageTimePlayer.exe 启动")
