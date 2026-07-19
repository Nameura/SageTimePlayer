# SageTimePlayer

基于 PySide6 的 Windows 桌面工具，集成代理管理与 Hanime1 视频浏览/播放功能。

## 功能

- **代理管理** — 多订阅管理（v2rayN 风格）、节点卡片展示、一键连接/断开
- **多核心支持** — Xray / Hysteria2 / Sing-Box 自动适配
- **节点测速** — 真连接延迟测试（颜色标识：绿 <200ms / 黄 <500ms / 红 >500ms）
- **订阅自动更新** — 可配置的定时自动刷新
- **视频浏览** — Hanime1 视频封面网格展示（支持搜索筛选）
- **视频播放** — 基于 mpv 的内置播放器，支持 1080p/720p/480p 清晰度切换
- **视频下载** — 直接下载到本地



## 快速开始

### 前置要求

- Windows 10/11 64位
- Python 3.10+
- 一个可用的代理订阅链接

### 克隆与安装

```bash
# 1. 克隆仓库到本地
git clone https://github.com/Nameura/SageTimePlayer.git

# 2. 进入项目目录
cd SageTimePlayer

# 3. 创建虚拟环境（避免依赖冲突）
python -m venv .venv
.venv\Scripts\activate

# 4. 安装 Python 依赖（PySide6、Scrapy 等）
pip install -r requirements.txt

# 5. 下载 mpv 播放依赖（libmpv-2.dll，约 110MB）
python scripts/download_mpv.py
```

### 运行

```bash
python main.py
```

### 打包 exe

```bash
python build_exe.py
```

打包产物在 `dist/SageTimePlayer/`，可直接分发（无需 Python 环境）。

## 项目结构

```
SageTimePlayer/
├── main.py                           # 入口
├── build_exe.py                      # PyInstaller 打包脚本
├── gui/                              # 界面组件
│   ├── main_window.py                # 主窗口
│   ├── sidebar.py                    # 侧边栏导航
│   ├── proxy/                        # 代理模块 UI
│   │   ├── proxy_page.py             # 代理管理页面
│   │   ├── node_card.py              # 节点卡片
│   │   ├── proxy_data.py             # 节点数据管理
│   │   └── subscription_dialog.py    # 订阅设置弹窗
│   └── video/                        # 视频模块 UI
│       ├── video_page.py             # 视频浏览页面
│       ├── video_play_page.py        # 视频播放页面
│       ├── cover_card.py             # 封面卡片
│       ├── mpv_player.py             # mpv 播放器封装
│       └── flow_layout.py            # 流式布局
├── proxy/                            # 代理后端
│   ├── fetch_nodes.py                # 订阅拉取与解析
│   ├── launch_v2ray.py               # 核心启动/停止
│   └── v2ray/                        # 代理核心文件
├── scrapy_core/                      # 爬虫
│   └── scrapy_spider/
│       ├── spiders/Hanime1_spider.py
│       ├── pipelines.py
│       └── settings.py
├── database/                         # 数据管理
│   ├── database.py                   # SQLite 操作
│   └── settings.py                   # JSON 配置读写
├── path/paths.py                     # 路径管理（开发/打包自动适配）
├── scripts/
│   └── download_mpv.py               # libmpv-2.dll 下载工具
└── assets/
    └── tools/libmpv-2.dll            # mpv 播放依赖（运行 download_mpv.py 自动下载）
```

## 技术栈

| 组件 | 技术 |
|:--|:--|
| GUI 框架 | PySide6 (Qt for Python) |
| 视频播放 | python-mpv + libmpv-2.dll |
| 爬虫 | Scrapy |
| 代理核心 | Xray-core, Hysteria2, Sing-Box |
| 数据存储 | SQLite (WAL 模式) |
| 打包 | PyInstaller |


## 后续更新
- 视频模块“加载更多视频”功能
- 设置模块相关内容
- 其他视频/插画网站的爬取（初步决定的有Pixiv，Iwara）
- 类似v2rayN的TUN模式（待确认是否需要）

## 免责声明

本软件仅供学习与技术交流使用。用户使用本软件进行的任何行为及后果均与本项目无关。
