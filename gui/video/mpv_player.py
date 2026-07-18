"""
mpv 播放器封装（基于 python-mpv + libmpv-2.dll）

将 mpv 嵌入到 Qt 窗口中，利用 mpv 自带的 OSC 实现控制栏淡入淡出和自动隐藏。
"""

import os
from pathlib import Path

# ── 在 import mpv 之前把 libmpv-2.dll 所在目录加入 PATH ──
_MPV_DLL_DIRS = [
    # 项目内嵌目录（打包场景或开发环境）
    str(Path(__file__).resolve().parent / "mpv"),
    str(Path(__file__).resolve().parent.parent.parent / "mpv"),
    str(Path(__file__).resolve().parent.parent.parent / "assets" / "tools"),
]
for _d in _MPV_DLL_DIRS:
    if os.path.isdir(_d) and any(
        os.path.isfile(os.path.join(_d, f))
        for f in ("libmpv-2.dll", "mpv-2.dll", "mpv-1.dll")
    ):
        os.environ.setdefault("PATH", "")
        if _d not in os.environ["PATH"]:
            os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]
        break

import mpv


class MpvPlayer:
    """
    mpv 播放器封装

    用法：
        player = MpvPlayer()
        player.set_container(hwnd)   # QWidget.winId()
        player.start(url)
        player.toggle_play()
        player.stop()
    """

    def __init__(self):
        self._mpv: mpv.MPV | None = None
        self._hwnd: int = 0
        self._on_end_cb = None
        self._on_loaded_cb = None

    def set_container(self, hwnd: int):
        """设置嵌入窗口的 HWND（QWidget.winId()）"""
        self._hwnd = hwnd

    def start(self, url: str) -> bool:
        """
        启动 mpv 并播放视频
        返回 True 表示成功
        """
        self.stop()

        if not self._hwnd:
            return False

        try:
            self._mpv = mpv.MPV(
                wid=str(self._hwnd),
                osc=True,                     # 启用 OSC 控制栏
                osd_level=1,
                osd_duration=2000,
                border=False,
                window_dragging=False,
                keepaspect_window=False,
                # 防盗链
                http_header_fields="Referer: https://hanime1.me",
                # 代理
                http_proxy="http://127.0.0.1:10909",
                # 用户代理
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/149.0.0.0",
                # 缓存
                cache=True,
                cache_secs=30,
                # 硬件加速
                hwdec="auto",
                gpu_context="auto",
            )

            # 注册事件回调
            @self._mpv.event_callback("end-file")
            def _on_end(event):
                if self._on_end_cb:
                    reason = getattr(event, "reason", None)
                    self._on_end_cb(reason)

            @self._mpv.event_callback("file-loaded")
            def _on_loaded(event):
                if self._on_loaded_cb:
                    self._on_loaded_cb()

            self._mpv.play(url)
            return True

        except Exception as e:
            print(f"[mpv] 启动失败: {e}")
            self._mpv = None
            return False

    def stop(self):
        """停止播放并释放资源"""
        if self._mpv:
            try:
                self._mpv.terminate()
            except Exception:
                pass
            self._mpv = None

    def restart(self, url: str) -> bool:
        """重新加载视频"""
        if self._mpv:
            try:
                self._mpv.play(url)
                return True
            except Exception as e:
                print(f"[mpv] 重新加载失败: {e}")
        return self.start(url)

    @property
    def is_running(self) -> bool:
        return self._mpv is not None

    # ── 回调 ────────────────────────────────────────────

    @property
    def on_end(self):
        return self._on_end_cb

    @on_end.setter
    def on_end(self, cb):
        self._on_end_cb = cb

    @property
    def on_file_loaded(self):
        return self._on_loaded_cb

    @on_file_loaded.setter
    def on_file_loaded(self, cb):
        self._on_loaded_cb = cb

    # ── 播放控制 ────────────────────────────────────────

    def play(self):
        if self._mpv:
            self._mpv.pause = False

    def pause(self):
        if self._mpv:
            self._mpv.pause = True

    def toggle_play(self):
        if self._mpv:
            self._mpv.pause = not self._mpv.pause

    def seek(self, pos_ms: int):
        if self._mpv:
            self._mpv.time_pos = pos_ms / 1000.0

    @property
    def volume(self) -> float:
        return (self._mpv.volume / 100.0) if self._mpv else 0.8

    @volume.setter
    def volume(self, val: float):
        if self._mpv:
            self._mpv.volume = max(0, min(100, int(val * 100)))

    @property
    def muted(self) -> bool:
        return self._mpv.mute if self._mpv else False

    @muted.setter
    def muted(self, val: bool):
        if self._mpv:
            self._mpv.mute = val

    def toggle_mute(self):
        if self._mpv:
            self._mpv.mute = not self._mpv.mute

    @property
    def time_pos(self) -> float:
        """当前播放位置（秒）"""
        return self._mpv.time_pos if self._mpv else 0.0

    @property
    def duration(self) -> float:
        """视频总时长（秒）"""
        return self._mpv.duration if self._mpv else 0.0

    @property
    def paused(self) -> bool:
        return self._mpv.pause if self._mpv else True
