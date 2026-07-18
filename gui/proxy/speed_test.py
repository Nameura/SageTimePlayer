"""
真连接测速

测速不启动代理，直接用 Python 的 socket 去连节点的服务器 IP:端口，测 TCP 握手时间。
通过 TCP 连接节点的 server:port 测量延迟，不依赖代理核心。
"""

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional


# 常用 HTTP 可达性探测目标
_TEST_URLS = [
    "https://www.google.com/generate_204",
    "https://www.youtube.com",
    "https://cloudflare.com/cdn-cgi/trace",
]


def tcp_ping(host: str, port: int, timeout: float = 2.0) -> Optional[float]:
    """TCP 连接测延迟（毫秒），超时返回 None"""
    # 采用微秒级的精度
    start = time.perf_counter()
    try:
        # 这个方法走的是TCP三次握手，基于UDP的节点就不行了
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        # 从秒转化成毫秒：0.083 秒 → 83 ms
        return (time.perf_counter() - start) * 1000
    except (socket.timeout, OSError):
        return None


def test_node_latency(node: dict, timeout: float = 2.0) -> Optional[float]:
    """测单个节点延迟"""
    host = node.get("server")
    port = node.get("port")
    if not host or not port:
        return None
    return tcp_ping(host, int(port), timeout)


def is_info_node(node: dict) -> bool:
    """判断是否为信息节点（非实际代理节点）"""
    name = node.get("name", "")
    return any(kw in name for kw in ["剩余流量", "距离下次", "套餐到期"])


def test_all_nodes(
    proxies: list[dict],
    max_workers: int = 20,
    timeout: float = 2.0,
    on_progress: callable = None,
) -> list[Optional[float]]:
    """并发测所有节点延迟，返回与 proxies 同顺序的列表"""
    # 预分配结果列表，长度与节点数相同，全部初始化为 None
    results: list[Optional[float]] = [None] * len(proxies)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {}
        for i, node in enumerate(proxies):
            # 跳过信息节点
            if is_info_node(node):
                results[i] = None
                continue
            host = node.get("server")
            port = node.get("port")
            if host and port:
                future = pool.submit(tcp_ping, host, int(port), timeout)
                future_map[future] = i
            else:
                results[i] = None

        total = len(future_map)
        done = 0
        # 迭代器，哪个线程先跑完就先返回哪个 future。比挨个调 future.result() 更高效。
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = None
            done += 1
            if on_progress:
                on_progress(done, total)

    return results


def verify_proxy_connectivity(proxy_host: str = "127.0.0.1", proxy_port: int = 10909, timeout: float = 10.0) -> bool:
    """验证本地代理是否可用（通过代理访问 Google）"""
    import urllib.request

    try:
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"http://{proxy_host}:{proxy_port}",
            "https": f"http://{proxy_host}:{proxy_port}",
        })
        opener = urllib.request.build_opener(proxy_handler)
        resp = opener.open("https://www.google.com/generate_204", timeout=timeout)
        return resp.status == 204
    except Exception:
        return False
