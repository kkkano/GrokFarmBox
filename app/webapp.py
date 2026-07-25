"""启动 Flask + 用 Chrome/Edge 的 --app 模式打开（桌面应用感，不依赖 WebView2）。"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from app.web_server import create_app

PORT = 8848
LOCK_PORT = 8849  # 单实例锁端口（绑定即持有，第二个实例绑不上就退出）
_singleton_sock = None  # 必须持有引用, 否则函数返回后 GC 关闭 socket → 锁失效


def _acquire_singleton() -> bool:
    """绑 LOCK_PORT 作为单例锁。已占用则打开已有 UI 并退出。"""
    global _singleton_sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        sock.listen(1)
        _singleton_sock = sock  # 存到全局, 防止 GC 关闭, 持有锁直到进程结束
        return True
    except OSError:
        print(f"已有实例在跑（{LOCK_PORT} 被占），打开现有 UI 并退出。")
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass
        sys.exit(0)


def _find_browser() -> str:
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return ""


def _open(url: str) -> None:
    time.sleep(1.2)
    exe = _find_browser()
    try:
        if exe:
            subprocess.Popen([exe, "--app=" + url, "--new-window"])
        else:
            webbrowser.open(url)
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def run() -> None:
    _acquire_singleton()  # 单实例：第二个实例直接退出
    app = create_app()
    url = f"http://127.0.0.1:{PORT}"
    threading.Thread(target=_open, args=(url,), daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run()
